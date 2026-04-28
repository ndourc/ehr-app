"""
API Layer — FastAPI route definitions
======================================
Endpoints
---------
  POST /api/v1/predict   Accept dual-stream EHR payload → prediction + XAI
  GET  /api/v1/health    Liveness check
  GET  /api/v1/records   Paginated audit log (role-filtered)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.guards import get_current_user, require_roles
from app.layers.ingestion.schemas import PredictRequest, PredictResponse
from app.layers.ingestion.validator import ValidationError, validate_request
from app.layers.output.predictor import InferenceResult, PredictionPipeline
from app.storage.database import get_db
from app.storage.models import AuditLog, PatientAssignment, PredictionRecord, User

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


async def _write_audit(
    db: AsyncSession,
    user_id: int,
    action: str,
    resource: str,
    request: Request,
) -> None:
    forwarded = request.headers.get("X-Forwarded-For")
    ip = forwarded.split(",")[0].strip() if forwarded else (
        request.client.host if request.client else "unknown"
    )
    db.add(AuditLog(user_id=user_id, action=action, resource=resource, ip_address=ip))


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
# POST /predict  —  clinician | analyst | admin only
# ─────────────────────────────────────────────────────────────────────────────
@router.post(
    "/predict",
    response_model=PredictResponse,
    status_code=status.HTTP_200_OK,
    tags=["Prediction"],
    summary="Predict psychological distress from combined EHR payload",
    responses={
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient role"},
        422: {"description": "Validation error (schema or semantic)"},
        503: {"description": "Pipeline not ready — train the model first"},
    },
)
async def predict(
    request: Request,
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    pipeline: PredictionPipeline = Depends(_get_pipeline),
    current_user: User = Depends(require_roles("clinician", "analyst", "admin")),
) -> PredictResponse:
    """
    Accept a combined JSON payload and return prediction + confidence + XAI.
    Requires clinician, analyst, or admin role.
    """
    # ── Layer 1: Extended semantic validation ─────────────────────────────
    try:
        validate_request(body)
    except ValidationError as exc:
        logger.warning("[Routes] Semantic validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    # ── Layers 2–4: Full inference pipeline ───────────────────────────────
    try:
        result: InferenceResult = pipeline.predict(body)
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

    now_utc = datetime.now(timezone.utc)

    # ── Storage: persist for auditability ─────────────────────────────────
    record = PredictionRecord(
        patient_id=result.patient_id,
        request_timestamp=body.timestamp.replace(tzinfo=timezone.utc)
        if body.timestamp.tzinfo is None
        else body.timestamp,
        raw_clinical_text=body.clinical_text,
        raw_structured_features=body.structured.model_dump(),
        cleaned_text=result.cleaned_text,
        normalised_structured=result.normalised_structured,
        prediction=result.prediction,
        confidence_score=result.confidence_score,
        important_tokens=[t.model_dump() for t in result.important_tokens],
        sentiment=result.sentiment,
        token_count=result.token_count,
        latency_ms=result.latency_ms,
        requested_by=current_user.username,
    )
    db.add(record)
    await _write_audit(db, current_user.id, "predict", f"/predict patient={result.patient_id}", request)
    await db.commit()

    logger.info(
        "[Routes] Prediction — patient_id=%s  by=%s  result=%s",
        result.patient_id, current_user.username, result.prediction,
    )

    response = result.to_response()
    response.requested_by = current_user.username
    response.timestamp = now_utc.isoformat()
    return response


# ─────────────────────────────────────────────────────────────────────────────
# GET /records — role-filtered audit log
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/records", tags=["Audit"], summary="Paginated prediction audit log")
async def list_records(
    request: Request,
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    limit: int | None = Query(None, ge=1, le=100),
    offset: int | None = Query(None, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Return paginated prediction records.

    Role visibility:
    - patient  : own records only (patient_profile_id)
    - clinician: assigned patients' records
    - analyst  : all records, de-identified (raw text / patient_id redacted)
    - admin    : all records, full detail
    """
    from sqlalchemy import func  # noqa: PLC0415

    await _write_audit(db, current_user.id, "list_records", "/records", request)
    await db.commit()

    # Resolve effective limit/offset
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

    # ── Build base query with role filters ────────────────────────────────
    base_stmt = select(PredictionRecord)

    if current_user.role == "patient":
        # Only own records
        own_pid = current_user.patient_profile_id or "__no_match__"
        base_stmt = base_stmt.where(PredictionRecord.patient_id == own_pid)
        if patient_id and patient_id != own_pid:
            return {"items": [], "total": 0, "page": eff_page, "page_size": eff_page_size}

    elif current_user.role == "clinician":
        # Assigned patients' profile IDs
        assign_stmt = select(User.patient_profile_id).join(
            PatientAssignment,
            PatientAssignment.patient_user_id == User.id,
        ).where(PatientAssignment.clinician_user_id == current_user.id)
        assigned_pids = list((await db.execute(assign_stmt)).scalars().all())
        base_stmt = base_stmt.where(PredictionRecord.patient_id.in_(assigned_pids))
        if patient_id:
            if patient_id not in assigned_pids:
                return {"items": [], "total": 0, "page": eff_page, "page_size": eff_page_size}
            base_stmt = base_stmt.where(PredictionRecord.patient_id == patient_id)

    else:
        # analyst / admin — unrestricted (analyst gets de-identified below)
        if patient_id:
            base_stmt = base_stmt.where(PredictionRecord.patient_id == patient_id)

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = base_stmt.order_by(desc(PredictionRecord.created_at)).limit(eff_limit).offset(eff_offset)
    rows = (await db.execute(stmt)).scalars().all()

    deidentify = current_user.role == "analyst"

    items = [
        {
            "id": r.id,
            "patient_id": f"ANON-{r.id}" if deidentify else r.patient_id,
            "prediction": r.prediction,
            "confidence_score": r.confidence_score,
            "important_tokens": r.important_tokens,
            "timestamp": r.request_timestamp.isoformat() if r.request_timestamp else None,
            "clinical_text": None if deidentify else r.raw_clinical_text,
            "sentiment": r.sentiment,
            "token_count": r.token_count,
            "latency_ms": r.latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "requested_by": r.requested_by,
        }
        for r in rows
    ]

    return {
        "items": items,
        "total": total,
        "page": eff_page,
        "page_size": eff_page_size,
    }

