"""
API Layer — FastAPI route definitions
======================================
Endpoints
---------
  POST /api/v1/predict   Accept dual-stream EHR payload → prediction + XAI
  GET  /api/v1/health    Liveness check
  GET  /api/v1/records   Paginated audit log (most recent first)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.layers.ingestion.schemas import PredictRequest, PredictResponse
from app.layers.ingestion.validator import ValidationError, validate_request
from app.layers.output.predictor import InferenceResult, PredictionPipeline
from app.storage.database import get_db
from app.storage.models import PredictionRecord

logger = logging.getLogger(__name__)
router = APIRouter()

# Injected at application startup by main.py
_pipeline: PredictionPipeline | None = None


def set_pipeline(pipeline: PredictionPipeline) -> None:
    global _pipeline
    _pipeline = pipeline


def _get_pipeline() -> PredictionPipeline:
    if _pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction pipeline not initialised. Restart the server.",
        )
    if not _pipeline.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "No trained classifier found. "
                "Run training/train.py then restart the server."
            ),
        )
    return _pipeline


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness probe — returns current UTC timestamp and pipeline status."""
    ready = _pipeline is not None and _pipeline.is_ready
    return {
        "status": "ok",
        "pipeline_ready": ready,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# POST /predict
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    tags=["Prediction"],
    summary="Predict psychological distress from combined EHR payload",
    responses={
        422: {"description": "Validation error (schema or semantic)"},
        503: {"description": "Pipeline not ready — train the model first"},
    },
)
async def predict(
    request: PredictRequest,
    db: AsyncSession = Depends(get_db),
    pipeline: PredictionPipeline = Depends(_get_pipeline),
) -> PredictResponse:
    """
    Accept a combined JSON payload of clinical text + 16 structured behavioural
    variables and return:

      * **prediction**       — "Distress" or "Stable"
      * **confidence_score** — probability of the predicted class [0.0, 1.0]
      * **important_tokens** — top-k attention-weighted words (XAI)

    Every inference event is persisted in PostgreSQL for clinical auditability.
    """
    # ── Layer 1: Extended semantic validation ─────────────────────────────
    try:
        validate_request(request)
    except ValidationError as exc:
        logger.warning("[Routes] Semantic validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # ── Layers 2–4: Full inference pipeline ───────────────────────────────
    try:
        result: InferenceResult = pipeline.predict(request)
    except RuntimeError as exc:
        logger.error("[Routes] Pipeline runtime error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        )
    except Exception:
        logger.exception("[Routes] Unexpected inference error.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal inference error. Check server logs.",
        )

    # ── Storage: persist for auditability ─────────────────────────────────
    record = PredictionRecord(
        patient_id=result.patient_id,
        request_timestamp=request.timestamp.replace(tzinfo=timezone.utc)
        if request.timestamp.tzinfo is None
        else request.timestamp,
        raw_clinical_text=request.clinical_text,
        raw_structured_features=request.structured.model_dump(),
        cleaned_text=result.cleaned_text,
        normalised_structured=result.normalised_structured,
        prediction=result.prediction,
        confidence_score=result.confidence_score,
        important_tokens=[t.model_dump() for t in result.important_tokens],
        sentiment=result.sentiment,
        token_count=result.token_count,
        latency_ms=result.latency_ms,
    )
    db.add(record)
    await db.commit()
    logger.info(
        "[Routes] Record stored — patient_id=%s  id=%s  prediction=%s",
        result.patient_id, record.id, result.prediction,
    )

    return result.to_response()


# ─────────────────────────────────────────────────────────────────────────────
# GET /records — audit log
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/records", tags=["Audit"], summary="Paginated prediction audit log")
async def list_records(
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    # Legacy params kept for backwards-compatibility
    limit: int | None = Query(None, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return paginated prediction records for audit purposes.
    Supports both page/page_size (frontend) and limit/offset (legacy) params.
    Optionally filter by patient_id.
    """
    from sqlalchemy import func  # noqa: PLC0415

    # Resolve effective limit/offset (page params take precedence)
    if limit is None and offset is None:
        eff_limit = page_size
        eff_offset = (page - 1) * page_size
        eff_page = page
        eff_page_size = page_size
    else:
        eff_limit = limit or page_size
        eff_offset = offset or 0
        eff_page_size = eff_limit
        eff_page = (eff_offset // eff_limit) + 1

    # Count total matching rows
    count_stmt = select(func.count(PredictionRecord.id))
    if patient_id:
        count_stmt = count_stmt.where(PredictionRecord.patient_id == patient_id)
    total: int = (await db.execute(count_stmt)).scalar_one()

    # Fetch rows
    stmt = select(PredictionRecord).order_by(desc(PredictionRecord.created_at))
    if patient_id:
        stmt = stmt.where(PredictionRecord.patient_id == patient_id)
    stmt = stmt.limit(eff_limit).offset(eff_offset)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        {
            "id": r.id,
            "patient_id": r.patient_id,
            "prediction": r.prediction,
            "confidence_score": r.confidence_score,
            "important_tokens": r.important_tokens,
            "timestamp": r.request_timestamp.isoformat() if r.request_timestamp else None,
            "clinical_text": r.raw_clinical_text,
            "sentiment": r.sentiment,
            "token_count": r.token_count,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": eff_page,
        "page_size": eff_page_size,
    }
