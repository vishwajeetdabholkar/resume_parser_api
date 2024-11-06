import os, sys
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any

from dotenv import load_dotenv
from loguru import logger

class Settings:
    """Simple configuration class for the application."""
    
    def __init__(self):
        # Load environment variables
        env_path = Path(__file__).resolve().parent.parent.parent / ".env"
        if not env_path.exists():
            raise FileNotFoundError(f".env file not found at {env_path}")
        load_dotenv(dotenv_path=env_path, override=True)
        logger.info(f"Loaded environment variables from {env_path}")

        logger.debug(f"OPENAI_API_KEY loaded: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
        
        # Set up base directories
        self.ROOT_DIR = Path(__file__).resolve().parent.parent.parent
        self.UPLOAD_DIR = self.ROOT_DIR / "uploads"
        self.TEMP_DIR = self.ROOT_DIR / "temp"
        self.LOG_DIR = self.ROOT_DIR / "logs"
        
        # Create necessary directories
        self._create_directories()
        
        # Project settings
        self.PROJECT_NAME = "Resume Parser API"
        self.VERSION = "1.0.0"
        self.API_V1_STR = "/api/v1"
        self.DEBUG = self._parse_bool(os.getenv("DEBUG", "False"))
        
        # External tools paths
        self.TESSERACT_PATH = str(self.ROOT_DIR / "Tesseract-OCR" / "tesseract.exe")
        self.POPPLER_PATH = str(self.ROOT_DIR / "poppler-23.11.0" / "Library" / "bin")
        
        # OpenAI settings
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002")
        self.GENERATE_EMBEDDINGS = os.getenv("GENERATE_EMBEDDINGS", "False").lower() == "true"
        self.MAX_TOKENS = int(os.getenv("MAX_TOKENS", "5000"))
        self.TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1"))
        
        # API settings
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        self.REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "30.0"))
        self.BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
        self.MAX_FILE_SIZE =  int("10485760")
        self.ALLOWED_FILE_TYPES = [".pdf"]
        
        # Performance settings
        self.WORKERS_COUNT = int(os.getenv("WORKERS_COUNT", "4"))
        self.ENABLE_ASYNC_PROCESSING = self._parse_bool(os.getenv("ENABLE_ASYNC_PROCESSING", "True"))
        
        # Logging settings
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_FORMAT = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        self.LOG_ROTATION = "20 MB"
        self.LOG_RETENTION = "1 month"
        
        # Feature flags
        self.ENABLE_OCR = self._parse_bool(os.getenv("ENABLE_OCR", "True"))
        self.ENABLE_TABLE_EXTRACTION = self._parse_bool(os.getenv("ENABLE_TABLE_EXTRACTION", "True"))
        self.ENABLE_LINK_EXTRACTION = self._parse_bool(os.getenv("ENABLE_LINK_EXTRACTION", "True"))
        self.ENABLE_BACKGROUND_TASKS = self._parse_bool(os.getenv("ENABLE_BACKGROUND_TASKS", "True"))
        
        # Cache settings
        self.CACHE_ENABLED = self._parse_bool(os.getenv("CACHE_ENABLED", "True"))
        self.CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
        
        # Validate critical settings
        self._validate_settings()

    def _clean_env_value(value: str) -> str:
        """Clean environment variable value by removing comments and whitespace."""
        return value.split('#')[0].strip() if value else value

    def _create_directories(self) -> None:
        """Create necessary directories if they don't exist."""
        try:
            self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
            self.LOG_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("All required directories created successfully")
        except Exception as e:
            logger.error(f"Error creating directories: {str(e)}")
            raise

    def _validate_settings(self) -> None:
        """Validate critical settings."""
        if not self.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set")
            
        if not os.path.exists(self.TESSERACT_PATH):
            logger.warning(f"Tesseract not found at {self.TESSERACT_PATH}")
            
        if not os.path.exists(self.POPPLER_PATH):
            logger.warning(f"Poppler not found at {self.POPPLER_PATH}")

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse string to boolean."""
        return value.lower() in ('true', '1', 't', 'yes', 'y')

    def configure_logging(self) -> None:
        """Configure loguru logger."""
        logger.configure(
            handlers=[
                {
                    "sink": str(self.LOG_DIR / "app.log"),
                    "level": self.LOG_LEVEL,
                    "format": self.LOG_FORMAT,
                    "rotation": self.LOG_ROTATION,
                    "retention": self.LOG_RETENTION,
                    "enqueue": True,
                },
                {
                    "sink": sys.stderr,
                    "level": self.LOG_LEVEL,
                    "format": self.LOG_FORMAT,
                },
            ]
        )
        logger.info("Logging configured successfully")

    def get_openai_config(self) -> Dict[str, Any]:
        """Get OpenAI-specific configuration."""
        return {
            "api_key": self.OPENAI_API_KEY,
            "default_model": self.DEFAULT_MODEL,
            "embedding_model": self.EMBEDDING_MODEL,
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.TEMPERATURE,
            "max_retries": self.MAX_RETRIES,
            "timeout": self.REQUEST_TIMEOUT,
        }

    def get_pdf_config(self) -> Dict[str, Any]:
        """Get PDF processing configuration."""
        return {
            "tesseract_path": self.TESSERACT_PATH,
            "poppler_path": self.POPPLER_PATH,
            "enable_ocr": self.ENABLE_OCR,
            "enable_table_extraction": self.ENABLE_TABLE_EXTRACTION,
            "enable_link_extraction": self.ENABLE_LINK_EXTRACTION,
            "max_file_size": self.MAX_FILE_SIZE,
            "allowed_file_types": self.ALLOWED_FILE_TYPES,
        }

@lru_cache()
def get_settings() -> Settings:
    """Create cached settings instance."""
    settings = Settings()
    settings.configure_logging()
    return settings