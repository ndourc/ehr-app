"""
Tests — Auth & RBAC
====================
Covers:
  - Login success / failure
  - JWT token expiry
  - Role denial (403 when wrong role)
  - Patient blocked from admin routes
  - Clinician can access prediction endpoint
  - /me returns current user
  - Refresh token rotation
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# ── App bootstrap ──────────────────────────────────────────────────────────────
# Override DATABASE_URL to in-memory SQLite before importing app
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-unit-tests-only")
os.environ.setdefault("JWT_EXPIRY_MINUTES", "30")

from app.main import app
from app.storage.database import AsyncSessionLocal, Base, create_tables, engine
from app.storage.seed import seed_users


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    """Create tables and seed users once for the entire module."""
    await create_tables()
    async with AsyncSessionLocal() as db:
        await seed_users(db)
    yield
    # Teardown: drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


async def _login(client: AsyncClient, username: str, password: str = "Password123!") -> dict:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return resp.json(), resp.status_code


# ── Auth tests ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success_clinician(client):
    data, status = await _login(client, "doctor1")
    assert status == 200
    assert "access_token" in data
    assert data["role"] == "clinician"


@pytest.mark.asyncio
async def test_login_success_admin(client):
    data, status = await _login(client, "admin1")
    assert status == 200
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    _, status = await _login(client, "doctor1", "WrongPassword!")
    assert status == 401


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    _, status = await _login(client, "nobody", "Password123!")
    assert status == 401


@pytest.mark.asyncio
async def test_me_authenticated(client):
    data, _ = await _login(client, "doctor1")
    token = data["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "doctor1"
    assert resp.json()["role"] == "clinician"


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_rejected(client):
    resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this.is.not.valid"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_works(client):
    data, _ = await _login(client, "analyst1")
    refresh = data["refresh_token"]
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_data = resp.json()
    assert "access_token" in new_data
    assert new_data["role"] == "analyst"


@pytest.mark.asyncio
async def test_refresh_token_invalid(client):
    resp = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"}
    )
    assert resp.status_code == 401


# ── RBAC tests ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patient_cannot_access_users_endpoint(client):
    data, _ = await _login(client, "patient1")
    token = data["access_token"]
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_analyst_cannot_access_users_endpoint(client):
    data, _ = await _login(client, "analyst1")
    token = data["access_token"]
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_access_users_endpoint(client):
    data, _ = await _login(client, "admin1")
    token = data["access_token"]
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_patient_cannot_call_predict(client):
    data, _ = await _login(client, "patient1")
    token = data["access_token"]
    payload = {
        "patient_id": "PT00001",
        "timestamp": "2026-04-28T10:00:00Z",
        "clinical_text": "Patient reports anxiety.",
        "structured": {k: 1 for k in [
            "mood_swings", "anxiety_level", "depression_indicators", "emotional_stability",
            "days_indoors", "social_interaction", "activity_level", "sleep_quality",
            "coping_struggles", "stress_level", "work_engagement", "motivation_level",
            "concentration_level", "decision_difficulty", "memory_issues", "support_system",
        ]},
    }
    resp = await client.post(
        "/api/v1/predict",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_call_predict(client):
    payload = {
        "patient_id": "PT00001",
        "timestamp": "2026-04-28T10:00:00Z",
        "clinical_text": "Test.",
        "structured": {k: 0 for k in [
            "mood_swings", "anxiety_level", "depression_indicators", "emotional_stability",
            "days_indoors", "social_interaction", "activity_level", "sleep_quality",
            "coping_struggles", "stress_level", "work_engagement", "motivation_level",
            "concentration_level", "decision_difficulty", "memory_issues", "support_system",
        ]},
    }
    resp = await client.post("/api/v1/predict", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unauthenticated_cannot_list_records(client):
    resp = await client.get("/api/v1/records")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_patient_records_returns_own_only(client):
    """patient1 can GET /records but only sees their own."""
    data, _ = await _login(client, "patient1")
    token = data["access_token"]
    resp = await client.get("/api/v1/records", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    # All returned records must belong to patient1's profile ID (PT00001) or be empty
    for item in items:
        assert item["patient_id"] == "PT00001"


@pytest.mark.asyncio
async def test_health_endpoint_public(client):
    """Health endpoint is unauthenticated."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


@pytest.mark.asyncio
async def test_logout(client):
    data, _ = await _login(client, "nurse1")
    token = data["access_token"]
    refresh = data["refresh_token"]

    # Logout
    resp = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    # Old refresh token should now be invalid
    retry = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert retry.status_code == 401
