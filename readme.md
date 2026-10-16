# Resume Parser API

A FastAPI service that turns a resume PDF into structured JSON. Text comes from the PDF itself (with OCR for scanned pages), and a Together AI serverless model fills a strict JSON schema.

## Quick start

```bash
cp .env.template .env        # then set TOGETHER_API_KEY
docker compose up -d --build
curl -F "file=@resume.pdf" localhost:8000/api/v1/resume/parse
```

Open <http://localhost:8000> for the web UI: product overview, getting-started guide, code snippets, the response schema, and a "Try it" panel to parse a resume in the browser. Interactive API docs are at <http://localhost:8000/docs>.

## How it works

```
PDF upload ─► validate (size, %PDF signature)
           ─► pdfplumber: text + hyperlinks per page        ┐ worker thread,
           ─► Tesseract OCR for pages with no text layer   ┘ bounded concurrency
           ─► Together chat completion with json_schema (primary model → fallback model)
           ─► Pydantic validation, experience calculation  ─► JSON response
```

Non-resume documents (invoices, letters, statements) are detected by the model and rejected with `422 not_a_resume`.

Fields the server owns are computed in code, not by the model: `duration_in_months`, `total_experience_in_years` (overlapping roles are merged, so nothing is double counted), and `end_date` for current roles. URLs from the model and from PDF hyperlinks are merged into `basics.urls`, and names are checked against the CV text to correct transcription slips.

## API

### `POST /api/v1/resume/parse`

Multipart form with a `file` field. Every successful response has the same fixed shape (see [`app/static/example.json`](app/static/example.json) for a full example):

```json
{
  "profile": {
    "basics": {
      "first_name": "Jean", "last_name": "Dujardin", "gender": "male",
      "emails": ["jean.dujardin@example.com"], "urls": ["linkedin.com/in/jean-dujardin"],
      "phone_numbers": ["1234567890"], "date_of_birth": {"year": 1992, "month": 7, "day": 14},
      "address": "1 Avenue des Champs-Élysées, 75008 Paris, France",
      "total_experience_in_years": 11, "profession": "AI Software Engineer",
      "summary": "...", "skills": ["Python", "Kubernetes"], "has_driving_license": true
    },
    "languages": [{"name": "French", "iso_code": "fr", "fluency": 5}],
    "educations": [{"start_year": 2012, "is_current": false, "end_year": 2015,
                    "issuing_organization": "École Polytechnique", "description": "Master in Computer Science"}],
    "trainings_and_certifications": [{"year": 2016, "issuing_organization": "Coursera", "description": "..."}],
    "professional_experiences": [{"start_date": {"year": 2015, "month": 7}, "is_current": true,
                                  "end_date": {"year": 2026, "month": 10}, "duration_in_months": 136,
                                  "company": "Mistral AI", "location": "Paris", "title": "Software Engineer",
                                  "description": "..."}],
    "awards": [{"year": 2023, "title": "...", "description": "..."}],
    "references": [{"full_name": "...", "phone_number": "...", "email": "...",
                    "company": "...", "position": "...", "description": "..."}]
  },
  "cv_language": "en",
  "cv_text": "Jean Dujardin\nAI Software Engineer\n..."
}
```

When a value is not in the CV, strings are `""`, lists are `[]`, and integers and enums are `null`. `gender` and `date_of_birth` are only filled when the CV states them explicitly; they are never inferred. `fluency` is 1 (elementary) to 5 (native).

Errors share one shape, and every response carries an `X-Request-ID` header (an incoming `X-Request-ID` is reused):

```json
{"request_id": "...", "error": {"code": "not_a_resume", "message": "The document does not appear to be a resume"}}
```

| Status | Code | Cause |
| --- | --- | --- |
| 400 | `invalid_request`, `invalid_pdf` | Missing file; corrupt or password-protected PDF |
| 413 | `file_too_large`, `too_many_pages` | Over `MAX_UPLOAD_MB` or `MAX_PAGES` |
| 415 | `unsupported_file_type` | Not a PDF |
| 422 | `no_text_found`, `not_a_resume` | Nothing readable; not a resume |
| 502 | `llm_auth_failed`, `llm_unavailable` | Bad API key; both models failed after retries |

### `GET /api/v1/resume/schema`

JSON Schema of the parse response, for generating typed clients.

### `GET /health`

Liveness probe, used by the Docker healthcheck.

## Configuration

Only `TOGETHER_API_KEY` is required. See [.env.template](.env.template) for every option and its default.

| Variable | Default | Notes |
| --- | --- | --- |
| `LLM_MODEL` | `nvidia/NVIDIA-Nemotron-3.5-Super-VL` | ~2-4 s, ~$0.001 per resume |
| `LLM_FALLBACK_MODEL` | `Qwen/Qwen3.5-9B` | Used when the primary fails; set empty to disable |
| `MAX_UPLOAD_MB` / `MAX_PAGES` | `10` / `10` | Request limits |
| `MAX_TEXT_CHARS` | `40000` | Caps tokens sent to the model |
| `MAX_CONCURRENT_PARSES` | `4` | PDF/OCR jobs per worker process |
| `WEB_CONCURRENCY` | `2` | Uvicorn worker processes |
| `DOCS_ENABLED` | `true` | Set `false` to hide `/docs` in production |
| `UI_ENABLED` | `true` | Set `false` to serve the API only |
| `CORS_ORIGINS` | `[]` | JSON list, e.g. `["https://app.example.com"]` |

Models must support structured outputs and be hosted by Together (models that need third-party data sharing are rejected for orgs with it disabled). Check the [serverless catalog](https://docs.together.ai/docs/serverless/models) and [deprecations](https://docs.together.ai/docs/deprecations) before changing them.

## Project layout

```
app/
├── main.py              # app setup, middleware, error handlers, /health
├── config.py            # settings from environment
├── routes.py            # POST /api/v1/resume/parse, GET /api/v1/resume/schema
├── schemas.py           # request/response and LLM output schemas
├── errors.py            # AppError -> JSON error response
├── static/              # web UI (plain HTML/CSS/JS, no build step)
└── services/
    ├── pdf.py           # text, link, and OCR extraction
    ├── extractor.py     # Together structured extraction with fallback
    └── profile.py       # server-owned fields: durations, total experience, URLs, names
tests/                   # unit + API tests (LLM is faked; no network)
```

## Development

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
ruff check . && ruff format --check .
```

Local runs need `tesseract` and `poppler` installed for OCR (`brew install tesseract poppler`); everything else works without them.

## Production notes

- The container runs as a non-root user on a read-only filesystem with a healthcheck.
- Put it behind a reverse proxy or load balancer that enforces a request body limit and TLS.
- Scale horizontally by adding containers; each one is stateless.
- Logs go to stdout with request IDs, model, token usage and latency, ready for any log collector.
