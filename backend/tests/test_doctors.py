import pytest
import jwt
import time
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.data_store import db_store

client = TestClient(app)


def make_token(user_id: str, email: str, role: str = "doctor", full_name: str = "Test Doctor") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "user_metadata": {
            "full_name": full_name,
            "role": role,
        },
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    secret = settings.SUPABASE_JWT_SECRET or "test-secret-key-12345"
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture(autouse=True)
def reset_database():
    db_store.seed_initial_data()


def test_list_doctors():
    token = make_token("user-1", "user1@example.com", role="patient")
    resp = client.get("/api/doctors", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    doctors = resp.json()
    assert len(doctors) >= 3
    doctor_names = [d["full_name"] for d in doctors]
    assert "Dr. Sarah Jenkins" in doctor_names
    assert "Dr. Marcus Vance" in doctor_names
    assert "Dr. Emily Chen" in doctor_names


def test_get_doctor_by_id():
    token = make_token("user-1", "user1@example.com", role="patient")
    resp = client.get("/api/doctors/doc-sarah-jenkins-01", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    doc = resp.json()
    assert doc["id"] == "doc-sarah-jenkins-01"
    assert doc["specialty"] == "Cardiology"


def test_get_doctor_availability():
    token = make_token("user-1", "user1@example.com", role="patient")
    resp = client.get("/api/doctors/doc-sarah-jenkins-01/availability", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    slots = resp.json()
    assert len(slots) >= 6  # Mon-Sat slots


def test_doctor_self_availability_management():
    # Doctor manages their own availability
    doc_token = make_token("doc-prof-sarah-jenkins", "dr.jenkins@careflow.ai", role="doctor", full_name="Dr. Sarah Jenkins")

    # 1. Get my profile
    me_resp = client.get("/api/doctor/me", headers={"Authorization": f"Bearer {doc_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["id"] == "doc-sarah-jenkins-01"

    # 2. Add Sunday slot (day 0)
    add_resp = client.post(
        "/api/doctor/me/availability",
        json={
            "day_of_week": 0,
            "start_time": "10:00",
            "end_time": "14:00",
            "is_active": True
        },
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    assert add_resp.status_code == 201
    slot_id = add_resp.json()["id"]
    assert add_resp.json()["day_name"] == "Sunday"

    # 3. Update slot
    upd_resp = client.put(
        f"/api/doctor/me/availability/{slot_id}",
        json={"start_time": "11:00"},
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    assert upd_resp.status_code == 200
    assert upd_resp.json()["start_time"] == "11:00"

    # 4. Delete slot
    del_resp = client.delete(
        f"/api/doctor/me/availability/{slot_id}",
        headers={"Authorization": f"Bearer {doc_token}"}
    )
    assert del_resp.status_code == 200
