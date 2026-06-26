"""Application configuration — all values from environment variables."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """App settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "Secure Translate"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "backend" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "backend" / "outputs"
    FONT_DIR: Path = BASE_DIR / "backend" / "fonts"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./secure_translate.db"

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # --- Translation Engines ---
    # Which engine to use by default: "gemini", "azure", "google"
    DEFAULT_TRANSLATION_ENGINE: str = "gemini"

    # Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Azure Translator
    AZURE_TRANSLATOR_KEY: Optional[str] = None
    AZURE_TRANSLATOR_REGION: Optional[str] = None
    AZURE_TRANSLATOR_ENDPOINT: str = "https://api.cognitive.microsofttranslator.com"

    # Google Cloud Translation
    GOOGLE_TRANSLATE_API_KEY: Optional[str] = None
    GOOGLE_PROJECT_ID: Optional[str] = None

    # --- OCR ---
    OCR_LANGUAGES: str = "en,ch"  # RapidOCR language codes
    OCR_USE_GPU: bool = False

    # --- Processing ---
    MAX_FILE_SIZE_MB: int = 100
    MAX_PAGES: int = 1000
    OCR_DPI: int = 300
    CHUNK_SIZE_CHARS: int = 4000  # Characters per translation chunk

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
