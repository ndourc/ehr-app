"""
Structured JSON logging configuration.
Call configure_logging() once at application startup.
"""
from __future__ import annotations

import logging
import logging.config
from pathlib import Path

from pythonjsonlogger import jsonlogger

from app.config import settings


def configure_logging() -> None:
    """
    Configure root logger to emit structured JSON to both stdout and a
    rotating log file under settings.LOG_DIR.
    All transformation logs from preprocessing pipeline flow through here.
    No silent preprocessing: every pipeline step logs its operation.
    """
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "ehr_engine.log"

    json_formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # ── File handler ──────────────────────────────────────────────────────
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(json_formatter)

    # ── Console handler ───────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter("[%(levelname)s] %(name)s — %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
