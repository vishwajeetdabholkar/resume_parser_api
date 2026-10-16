import pytest

from app.errors import AppError
from app.services import pdf
from tests.conftest import RESUME_LINES, make_pdf


def test_extracts_text_and_links():
    content = pdf.extract(make_pdf(RESUME_LINES), max_pages=5, ocr_enabled=False)

    assert content.pages == 1 and content.ocr_pages == 0
    assert "Acme Corp, Staff Engineer" in content.text
    assert content.links == ["github.com/janedoe", "janedoe.dev"]


def test_rejects_corrupt_pdf():
    with pytest.raises(AppError) as exc:
        pdf.extract(b"%PDF-1.4 garbage", max_pages=5, ocr_enabled=False)
    assert exc.value.code == "invalid_pdf"


def test_rejects_too_many_pages():
    with pytest.raises(AppError) as exc:
        pdf.extract(make_pdf(["hello"], pages=3), max_pages=2, ocr_enabled=False)
    assert exc.value.status_code == 413


def test_clean_text_collapses_whitespace_and_bullets():
    raw = "Name\t\tSurname  \n•\n\n\n\nSkills:  Python ,  C++"
    assert pdf.clean_text(raw) == "Name Surname\n\nSkills: Python , C++"


def test_normalize_links():
    raw = ["www.site.com/", "mailto:a@b.com", "https://x.dev/path).", "https://linkedin.com/in/jane", "tel:123"]
    assert pdf.normalize_links(raw) == ["linkedin.com/in/jane", "site.com", "x.dev/path"]
