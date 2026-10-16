import os

os.environ["TOGETHER_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routes import get_extractor
from app.schemas import Basics, Extraction, ProfessionalExperience, Profile, YearMonth
from app.services.extractor import ExtractionResult


def make_pdf(lines: list[str], pages: int = 1) -> bytes:
    """Build a minimal valid PDF with the given text lines on every page."""
    escaped = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    stream = ("BT /F1 11 Tf 72 720 Td 14 TL " + " ".join(f"({line}) '" for line in escaped) + " ET").encode()

    page_ids = [4 + i for i in range(pages)]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % i for i in page_ids), pages),
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        *(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 3 0 R "
            b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (4 + pages)
            for _ in range(pages)
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref_at)
    return bytes(out)


RESUME_LINES = [
    "Jane Doe - Senior Backend Engineer",
    "jane@example.com | github.com/janedoe | https://janedoe.dev",
    "EXPERIENCE",
    "Acme Corp, Staff Engineer, 2022-01 to Present",
    "Globex, Software Engineer, 2018-06 to 2021-12",
    "EDUCATION: B.Tech Computer Science, IIT Bombay, 2014-2018",
    "SKILLS: Python, Go, Kubernetes, PostgreSQL",
]


class FakeExtractor:
    def __init__(self, extraction: Extraction | None = None, error: Exception | None = None) -> None:
        self.extraction = extraction
        self.error = error
        self.calls: list[str] = []

    async def extract(self, text: str) -> ExtractionResult:
        self.calls.append(text)
        if self.error:
            raise self.error
        return ExtractionResult(self.extraction, model="fake-model", prompt_tokens=120, completion_tokens=80)


@pytest.fixture
def extraction() -> Extraction:
    return Extraction(
        is_resume=True,
        cv_language="en",
        profile=Profile(
            basics=Basics(
                first_name="Jane",
                last_name="Doe",
                emails=["jane@example.com"],
                urls=["https://www.linkedin.com/in/janedoe/"],
                skills=["Python", "Go"],
            ),
            professional_experiences=[
                ProfessionalExperience(company="Acme Corp", start_date=YearMonth(year=2022, month=1), is_current=True),
                ProfessionalExperience(
                    company="Globex", start_date=YearMonth(year=2018, month=6), end_date=YearMonth(year=2021, month=12)
                ),
            ],
        ),
    )


@pytest.fixture
def resume_pdf() -> bytes:
    return make_pdf(RESUME_LINES)


@pytest.fixture
def client_with():
    """Return a factory that builds a TestClient wired to the given fake extractor."""
    clients = []

    def build(extractor: FakeExtractor) -> TestClient:
        app.dependency_overrides[get_extractor] = lambda: extractor
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield build
    for client in clients:
        client.__exit__(None, None, None)
    app.dependency_overrides.clear()
