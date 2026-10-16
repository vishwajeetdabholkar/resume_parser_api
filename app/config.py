from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    together_api_key: SecretStr = Field(min_length=1)
    llm_model: str = "nvidia/NVIDIA-Nemotron-3.5-Super-VL"
    llm_fallback_model: str | None = "Qwen/Qwen3.5-9B"
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    llm_max_tokens: int = 4096

    max_upload_mb: int = 10
    max_pages: int = 10
    max_text_chars: int = 40_000
    max_concurrent_parses: int = 4
    ocr_enabled: bool = True

    log_level: str = "INFO"
    docs_enabled: bool = True
    ui_enabled: bool = True
    cors_origins: list[str] = []

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
