from functools import lru_cache

from fastapi import Depends

from app.core.config import get_settings
from app.services.pdf import PDFService
from app.services.ai import AIService, AIServiceConfig

@lru_cache()
def get_pdf_service() -> PDFService:
    """
    Create or return cached instance of PDFService.
    """
    return PDFService()

@lru_cache()
def get_ai_service() -> AIService:
    """
    Create or return cached instance of AIService.
    """
    settings = get_settings()
    config = AIServiceConfig(
        api_key=settings.OPENAI_API_KEY,
        default_model=settings.DEFAULT_MODEL,
        embedding_model=settings.EMBEDDING_MODEL,
        max_retries=settings.MAX_RETRIES,
        timeout=settings.REQUEST_TIMEOUT,
        debug_mode=settings.DEBUG,
        generate_embeddings=settings.GENERATE_EMBEDDINGS 
    )
    return AIService(config)