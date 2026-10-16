import json
from pathlib import Path

from app.config import get_settings
from app.errors import AppError
from app.main import app
from app.schemas import Extraction
from tests.conftest import FakeExtractor, make_pdf

URL = "/api/v1/resume/parse"


def upload(client, data: bytes, name: str = "cv.pdf"):
    return client.post(URL, files={"file": (name, data, "application/pdf")})


def test_parse_returns_fixed_format(client_with, extraction, resume_pdf):
    extractor = FakeExtractor(extraction)
    response = upload(client_with(extractor), resume_pdf)

    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["profile", "cv_language", "cv_text"]
    assert list(body["profile"]) == [
        "basics",
        "languages",
        "educations",
        "trainings_and_certifications",
        "professional_experiences",
        "awards",
        "references",
    ]
    basics = body["profile"]["basics"]
    assert basics["first_name"] == "Jane" and basics["gender"] is None and basics["address"] == ""
    assert basics["date_of_birth"] == {"year": None, "month": None, "day": None}
    assert basics["total_experience_in_years"] >= 8
    assert basics["urls"] == ["github.com/janedoe", "janedoe.dev", "linkedin.com/in/janedoe"]
    current = body["profile"]["professional_experiences"][0]
    assert current["end_date"]["year"] is not None and current["duration_in_months"] > 0
    assert body["cv_language"] == "en"
    assert "Acme Corp" in body["cv_text"] and "Acme Corp" in extractor.calls[0]
    assert response.headers["x-request-id"]


def test_request_id_is_propagated(client_with, extraction, resume_pdf):
    client = client_with(FakeExtractor(extraction))
    response = client.post(URL, files={"file": ("cv.pdf", resume_pdf)}, headers={"X-Request-ID": "abc123"})
    assert response.headers["x-request-id"] == "abc123"


def test_not_a_resume(client_with, resume_pdf):
    response = upload(client_with(FakeExtractor(Extraction(is_resume=False))), resume_pdf)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_a_resume"


def test_rejects_non_pdf(client_with):
    extractor = FakeExtractor()
    response = upload(client_with(extractor), b"PK\x03\x04 not a pdf", name="cv.docx")
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"
    assert extractor.calls == []


def test_rejects_oversized_upload(client_with, resume_pdf):
    app.dependency_overrides[get_settings] = lambda: get_settings().model_copy(update={"max_upload_mb": 1})
    response = upload(client_with(FakeExtractor()), resume_pdf + b"0" * (1024 * 1024))
    assert response.status_code == 413


def test_rejects_pdf_without_text(client_with):
    response = upload(client_with(FakeExtractor()), make_pdf(["hi"]))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_text_found"


def test_missing_file(client_with):
    response = client_with(FakeExtractor()).post(URL)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


def test_llm_failure_maps_to_502(client_with, resume_pdf):
    error = AppError(502, "llm_unavailable", "Resume extraction failed; please retry later")
    response = upload(client_with(FakeExtractor(error=error)), resume_pdf)
    assert response.status_code == 502
    assert response.json()["error"] == {"code": "llm_unavailable", "message": error.message}


def test_health(client_with):
    assert client_with(FakeExtractor()).get("/health").json()["status"] == "ok"


def test_schema_endpoint(client_with):
    schema = client_with(FakeExtractor()).get("/api/v1/resume/schema").json()
    assert schema["required"] == ["profile", "cv_language", "cv_text"]


def test_ui_is_served_without_shadowing_api(client_with):
    client = client_with(FakeExtractor())
    assert "ResumeParser" in client.get("/").text
    assert client.get("/app.js").status_code == 200
    assert client.get("/health").json()["status"] == "ok"


def test_llm_output_with_nulls_still_yields_full_format():
    raw = {"is_resume": True, "cv_language": None, "profile": {"basics": {"first_name": None, "skills": None}}}
    profile = Extraction.model_validate_json(json.dumps(raw)).profile
    assert profile.basics.first_name == "" and profile.basics.skills == [] and profile.references == []


def test_example_in_ui_matches_response_schema():
    """The UI's data example must stay valid against the real response model."""
    from app.schemas import ParseResponse

    source = (Path(__file__).parents[1] / "app/static/example.json").read_text()
    ParseResponse.model_validate_json(source)
