"""
FastAPI Application Entry Point
=================================
Startup sequence:
  1. Configure structured JSON logging.
  2. Create PostgreSQL tables (idempotent).
  3. Load ClinicalBERT + trained classifier into the PredictionPipeline.
  4. Register API router.

Run:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router, set_pipeline
from app.layers.output.predictor import PredictionPipeline
from app.storage.database import create_tables
from app.utils.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Manage application startup and shutdown lifecycle."""
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("Sentiment-Aware EHR Predictive Engine — starting up")
    logger.info("=" * 60)

    # Initialise database schema
    await create_tables()

    # Load models once; share across all requests
    pipeline = PredictionPipeline()
    set_pipeline(pipeline)

    if pipeline.is_ready:
        logger.info("Pipeline is READY — serving predictions.")
    else:
        logger.warning(
            "Pipeline is in DEGRADED MODE — no trained classifier found. "
            "Run  training/train.py  then restart."
        )

    yield  # ← application runs here

    logger.info("EHR Predictive Engine — shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# Application instance
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Sentiment-Aware EHR Predictive Engine",
    description=(
        "Real-time hybrid ML system for psychological distress prediction "
        "from clinical notes + structured behavioural metrics."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow same-origin requests in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
