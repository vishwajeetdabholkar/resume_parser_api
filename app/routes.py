import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.config import Settings, get_settings
from app.errors import AppError
from app.schemas import ErrorResponse, ParseResponse
from app.services import pdf
from app.services.extractor import ResumeExtractor
from app.services.profile import finalize_profile

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/resume", tags=["resume"])

MIN_TEXT_CHARS = 100


@router.get("/schema", summary="JSON Schema of the parse response")
async def response_schema() -> dict[str, Any]:
    return ParseResponse.model_json_schema()


def get_extractor(request: Request) -> ResumeExtractor:
    return request.app.state.extractor


async def read_pdf_upload(file: UploadFile, max_bytes: int) -> bytes:
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise AppError(413, "file_too_large", f"File exceeds the {max_bytes // (1024 * 1024)} MB limit")
    if not data.startswith(b"%PDF-"):
        raise AppError(415, "unsupported_file_type", "Only PDF files are supported")
    return data


@router.post(
    "/parse",
    response_model=ParseResponse,
    responses={code: {"model": ErrorResponse} for code in (400, 413, 415, 422, 502)},
)
async def parse_resume(
    request: Request,
    file: UploadFile = File(..., description="Resume as a PDF"),
    settings: Settings = Depends(get_settings),
    extractor: ResumeExtractor = Depends(get_extractor),
) -> ParseResponse:
    started = time.perf_counter()
    data = await read_pdf_upload(file, settings.max_upload_bytes)

    async with request.app.state.parse_slots:
        content = await run_in_threadpool(
            pdf.extract, data, max_pages=settings.max_pages, ocr_enabled=settings.ocr_enabled
        )
    if len(content.text) < MIN_TEXT_CHARS:
        raise AppError(422, "no_text_found", "No readable text found in the PDF")

    result = await extractor.extract(content.text[: settings.max_text_chars])
    if not result.extraction.is_resume:
        raise AppError(422, "not_a_resume", "The document does not appear to be a resume")

    log.info(
        "Parsed resume model=%s pages=%d ocr_pages=%d tokens=%d+%d in %dms",
        result.model,
        content.pages,
        content.ocr_pages,
        result.prompt_tokens,
        result.completion_tokens,
        (time.perf_counter() - started) * 1000,
    )
    return ParseResponse(
        profile=finalize_profile(result.extraction.profile, content.text, content.links),
        cv_language=result.extraction.cv_language,
        cv_text=content.text,
    )
