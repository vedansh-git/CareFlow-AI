import jwt
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)


def create_mock_jwt(user_id: str = "test-user-uuid-123", email: str = "testpatient@example.com", role: str = "patient"):
    """Helper to generate a valid mock Supabase JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "user_metadata": {
            "full_name": "Test Patient",
            "role": role,
        },
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    secret = settings.SUPABASE_JWT_SECRET or "test-secret-key-12345"
    return jwt.encode(payload, secret, algorithm="HS256")


def test_me_endpoint_without_token():
    """Verify GET /api/me rejects requests missing authorization header with 401."""
    response = client.get("/api/me")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_me_endpoint_with_invalid_token():
    """Verify GET /api/me rejects invalid bearer tokens with 401."""
    response = client.get(
        "/api/me",
        headers={"Authorization": "Bearer invalid.token.string"}
    )
    assert response.status_code == 401


def test_me_endpoint_with_expired_token():
    """Verify GET /api/me rejects expired tokens with 401."""
    expired_payload = {
        "sub": "test-user-uuid",
        "email": "test@example.com",
        "exp": int(time.time()) - 3600,
    }
    secret = settings.SUPABASE_JWT_SECRET or "test-secret-key-12345"
    expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401


def test_me_endpoint_with_valid_jwt():
    """Verify GET /api/me returns 200 OK and user identity when provided a valid token."""
    token = create_mock_jwt(user_id="user-789", email="patient789@careflow.ai", role="patient")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "user-789"
    assert data["email"] == "patient789@careflow.ai"
    assert data["role"] == "patient"
    assert data["authenticated"] is True


def test_me_endpoint_with_doctor_jwt():
    """Verify GET /api/me returns role='doctor' when doctor role is supplied."""
    token = create_mock_jwt(user_id="doc-999", email="dr.smith@careflow.ai", role="doctor")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "doc-999"
    assert data["email"] == "dr.smith@careflow.ai"
    assert data["role"] == "doctor"
    assert data["authenticated"] is True


def test_me_endpoint_prevents_admin_metadata_escalation():
    """Verify that unverified client metadata claiming 'admin' is sanitized to 'patient'."""
    token = create_mock_jwt(user_id="attacker-007", email="hacker@evil.com", role="admin")

    response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    # Must NOT grant admin role from unverified token metadata
    assert data["role"] == "patient"

