"""
FastAPI Application Entry Point
=================================
Startup sequence:
  1. Configure structured JSON logging.
  2. Create database tables (idempotent).
  3. Seed default development users.
  4. Load ClinicalBERT + trained classifier into the PredictionPipeline.
  5. Register API routers.

Run:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router, set_pipeline
from app.auth.routes import router as auth_router
from app.layers.output.predictor import PredictionPipeline
from app.storage.database import AsyncSessionLocal, create_tables
from app.storage.seed import seed_users
from app.users.routes import router as users_router
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

    # Seed development users
    async with AsyncSessionLocal() as db:
        await seed_users(db)

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
        "Secure clinical intelligence platform with hybrid ML distress prediction, "
        "role-based access control, and explainability outputs."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# In production, replace "*" with your frontend origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(router, prefix="/api/v1")

