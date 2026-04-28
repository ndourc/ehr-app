"""
Central application configuration.
All settings are read from environment variables or a .env file.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "sqlite+aiosqlite:///./ehr_db.sqlite3"
    )

    # ── Model ─────────────────────────────────────────────────────────────
    CLINICALBERT_MODEL: str = "medicalai/ClinicalBERT"
    ARTIFACTS_DIR: str = str(BASE_DIR / "artifacts")

    # ── Logging ───────────────────────────────────────────────────────────
    LOG_DIR: str = str(BASE_DIR / "logs")
    LOG_LEVEL: str = "INFO"

    # ── Inference ─────────────────────────────────────────────────────────
    MAX_TOKEN_LENGTH: int = 512
    DISTRESS_CLASS_WEIGHT: float = 3.0
    ATTENTION_TOP_K: int = 10

    # ── Auth / JWT ────────────────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRY_DAYS: int = 7


settings = Settings()
