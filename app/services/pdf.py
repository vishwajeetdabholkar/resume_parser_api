import io
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass

import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes

from app.errors import AppError

log = logging.getLogger(__name__)

# Pages with less selectable text than this are treated as scanned images and OCR'd.
MIN_PAGE_CHARS = 50
OCR_DPI = 300

URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:linkedin\.com|github\.com)/\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[^\s/@]+@[^\s/@]+")


@dataclass(frozen=True)
class PdfContent:
    text: str
    links: list[str]
    pages: int
    ocr_pages: int


def extract(data: bytes, *, max_pages: int, ocr_enabled: bool) -> PdfContent:
    """Extract text and links from a PDF. CPU-bound: call from a worker thread."""
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as exc:
        raise AppError(400, "invalid_pdf", "Could not read the PDF (corrupt or password-protected)") from exc

    with pdf:
        page_count = len(pdf.pages)
        if page_count == 0:
            raise AppError(400, "invalid_pdf", "The PDF has no pages")
        if page_count > max_pages:
            raise AppError(413, "too_many_pages", f"PDF has {page_count} pages; the limit is {max_pages}")

        texts, links, ocr_pages = [], set(), 0
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if ocr_enabled and len(text.strip()) < MIN_PAGE_CHARS:
                ocr_text = _ocr_page(data, number)
                if ocr_text.strip():
                    text, ocr_pages = ocr_text, ocr_pages + 1
            texts.append(text)
            links.update(link["uri"] for link in page.hyperlinks if link.get("uri"))

    text = clean_text("\n\n".join(texts))
    links.update(URL_RE.findall(text))
    return PdfContent(text=text, links=normalize_links(links), pages=page_count, ocr_pages=ocr_pages)


def _ocr_page(data: bytes, page_number: int) -> str:
    try:
        images = convert_from_bytes(data, dpi=OCR_DPI, first_page=page_number, last_page=page_number)
        return pytesseract.image_to_string(images[0]) if images else ""
    except Exception:
        log.warning("OCR failed for page %d", page_number, exc_info=True)
        return ""


def clean_text(text: str) -> str:
    lines = (re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines())
    text = "\n".join(line for line in lines if line not in {"•", "·", "-", "*"})
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize_links(raw: Iterable[str]) -> list[str]:
    """Deduplicate URLs in the compact form 'linkedin.com/in/jane' (no scheme, no www)."""
    links: dict[str, str] = {}
    for url in raw:
        url = re.sub(r"^(?:https?://)?(?:www\.)?", "", url.strip(), flags=re.IGNORECASE).rstrip(".,;:)]}>\"'/")
        if not url or url.lower().startswith(("mailto:", "tel:")) or EMAIL_RE.fullmatch(url):
            continue
        host, slash, path = url.partition("/")
        url = f"{host.lower()}{slash}{path}"
        links.setdefault(url.lower(), url)
    return sorted(links.values(), key=str.lower)
