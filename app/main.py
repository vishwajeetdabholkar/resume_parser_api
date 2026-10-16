import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.errors import AppError
from app.routes import router
from app.services.extractor import ResumeExtractor

VERSION = "2.0.0"

settings = get_settings()
logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
)
log = logging.getLogger("app")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


for handler in logging.getLogger().handlers:
    handler.addFilter(_RequestIdFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.extractor = ResumeExtractor(settings)
    app.state.parse_slots = asyncio.Semaphore(settings.max_concurrent_parses)
    log.info("Started v%s with model=%s fallback=%s", VERSION, settings.llm_model, settings.llm_fallback_model)
    yield
    await app.state.extractor.aclose()


app = FastAPI(
    title="Resume Parser API",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
if settings.cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request.state.request_id = request_id
    token = request_id_var.set(request_id)
    started = time.perf_counter()
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if request.url.path.startswith("/api/"):
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            log.info("%s %s -> %d in %dms", request.method, request.url.path, response.status_code, elapsed_ms)
        return response
    finally:
        request_id_var.reset(token)


def _error(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status_code,
        content={"request_id": request_id, "error": {"code": code, "message": message}},
        headers={"X-Request-ID": request_id} if request_id else None,
    )


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return _error(request, exc.status_code, exc.code, exc.message)


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"][1:]) or "request"
    return _error(request, 400, "invalid_request", f"{field}: {first['msg']}")


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error")
    return _error(request, 500, "internal_error", "An unexpected error occurred")


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok", "version": VERSION}


# Mounted last: a mount at "/" would otherwise shadow every route registered after it.
if settings.ui_enabled:
    app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="ui")
