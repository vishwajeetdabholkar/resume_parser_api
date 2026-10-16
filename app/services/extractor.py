import json
import logging
from dataclasses import dataclass

from pydantic import ValidationError
from together import APIError, AsyncTogether, AuthenticationError

from app.config import Settings
from app.errors import AppError
from app.schemas import Extraction

log = logging.getLogger(__name__)

EXTRACTION_SCHEMA = Extraction.model_json_schema()

SYSTEM_PROMPT = f"""You extract structured data from CV / resume text.
Rules:
- Use only information present in the text. Never guess or invent values.
- When a value is absent: strings are "", lists are [], numbers and enums are null.
- Never infer gender or date of birth; fill them only when the CV states them explicitly.
- Dates: year as a 4-digit integer, month as 1-12. Leave month null when the CV gives only a year.
- For a current role set is_current=true and leave end_date year and month null.
- Write descriptions in the CV's language, keeping one responsibility or achievement per line.
- If the document is not a resume or CV (invoice, letter, statement, etc.), set is_resume=false
  and leave everything else empty.
Respond with JSON only, matching this schema:
{json.dumps(EXTRACTION_SCHEMA)}"""


@dataclass(frozen=True)
class ExtractionResult:
    extraction: Extraction
    model: str
    prompt_tokens: int
    completion_tokens: int


class ResumeExtractor:
    def __init__(self, settings: Settings) -> None:
        self._client = AsyncTogether(
            api_key=settings.together_api_key.get_secret_value(),
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        self._models = [m for m in (settings.llm_model, settings.llm_fallback_model) if m]
        self._max_tokens = settings.llm_max_tokens

    async def extract(self, text: str) -> ExtractionResult:
        """Try each configured model in order; the SDK already retries transient errors per model."""
        for model in self._models:
            try:
                return await self._extract_with(model, text)
            except AuthenticationError as exc:
                raise AppError(502, "llm_auth_failed", "LLM provider rejected the API key") from exc
            except (APIError, ValidationError, ValueError) as exc:
                log.warning("Extraction with %s failed: %s", model, exc)
        raise AppError(502, "llm_unavailable", "Resume extraction failed; please retry later")

    async def _extract_with(self, model: str, text: str) -> ExtractionResult:
        response = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "cv_extraction", "schema": EXTRACTION_SCHEMA},
            },
            # Hybrid models reason by default and can spend the whole token budget before emitting JSON.
            reasoning={"enabled": False},
            temperature=0,
            max_tokens=self._max_tokens,
        )
        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise ValueError("empty completion")
        usage = response.usage
        return ExtractionResult(
            extraction=Extraction.model_validate_json(content),
            model=model,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    async def aclose(self) -> None:
        await self._client.close()
