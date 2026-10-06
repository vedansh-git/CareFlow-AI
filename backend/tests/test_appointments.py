import pytest
import jwt
import time
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.services.data_store import db_store, get_db_day_of_week

client = TestClient(app)


def make_token(user_id: str, email: str, role: str = "patient", full_name: str = "Test User") -> str:
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
    """Reset data store before each test run for complete isolation."""
    db_store.seed_initial_data()


def get_next_weekday_date(day_of_week: int = 1) -> str:
    """Finds the next upcoming date matching day_of_week (e.g. 1 = Monday)."""
    today = date.today() + timedelta(days=1)
    for i in range(14):
        candidate = today + timedelta(days=i)
        if get_db_day_of_week(candidate) == day_of_week:
            return candidate.strftime("%Y-%m-%d")
    return (today + timedelta(days=7)).strftime("%Y-%m-%d")


def test_unauthenticated_appointment_request():
    """1. Unauthenticated appointment request returns 401."""
    resp = client.get("/api/appointments")
    assert resp.status_code == 401

    post_resp = client.post("/api/appointments", json={
        "doctor_id": "doc-sarah-jenkins-01",
        "appointment_date": "2026-10-05",
        "start_time": "10:00",
        "end_time": "10:30",
        "reason": "Checkup"
    })
    assert post_resp.status_code == 401


def test_patient_can_create_valid_appointment():
    """4. Patient can create a valid appointment (201 Created)."""
    token = make_token("patient-user-1", "patient1@example.com", role="patient", full_name="Alice Patient")
    monday_date = get_next_weekday_date(1)  # Next Monday

    payload = {
        "doctor_id": "doc-sarah-jenkins-01",
        "appointment_date": monday_date,
        "start_time": "10:00",
        "end_time": "10:30",
        "reason": "Routine Cardiology Consultation"
    }

    resp = client.post(
        "/api/appointments",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["doctor_id"] == "doc-sarah-jenkins-01"
    assert data["appointment_date"] == monday_date
    assert data["start_time"] == "10:00"
    assert data["end_time"] == "10:30"
    assert data["status"] == "scheduled"
    assert data["doctor_name"] == "Dr. Sarah Jenkins"
    assert data["patient_name"] == "Alice Patient"


def test_patient_can_retrieve_own_appointments():
    """2. Patient can retrieve own appointments."""
    token = make_token("patient-user-2", "patient2@example.com", role="patient", full_name="Bob Patient")
    monday_date = get_next_weekday_date(1)

    # Book appointment
    client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "11:00",
            "end_time": "11:30",
            "reason": "Chest check"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    resp = client.get(
        "/api/appointments",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["reason"] == "Chest check"


def test_patient_cannot_retrieve_another_patients_appointment():
    """3. Patient cannot retrieve another patient's appointment (403 Forbidden)."""
    alice_token = make_token("patient-alice", "alice@example.com", role="patient")
    bob_token = make_token("patient-bob", "bob@example.com", role="patient")
    monday_date = get_next_weekday_date(1)

    # Alice books an appointment
    create_resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "09:30",
            "end_time": "10:00",
            "reason": "Alice private exam"
        },
        headers={"Authorization": f"Bearer {alice_token}"}
    )
    assert create_resp.status_code == 201
    appt_id = create_resp.json()["id"]

    # Bob attempts to read Alice's appointment by ID
    bob_resp = client.get(
        f"/api/appointments/{appt_id}",
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert bob_resp.status_code == 403
    assert "Unauthorized" in bob_resp.json()["detail"]


def test_duplicate_conflicting_appointment():
    """5. Duplicate/conflicting appointment returns 409 Conflict."""
    token1 = make_token("user-p1", "p1@example.com", role="patient")
    token2 = make_token("user-p2", "p2@example.com", role="patient")
    monday_date = get_next_weekday_date(1)

    # User 1 books 14:00 - 14:30 with Dr. Jenkins
    resp1 = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "14:00",
            "end_time": "14:30",
            "reason": "First booking"
        },
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp1.status_code == 201

    # User 2 attempts to book overlapping slot (14:15 - 14:45) with same doctor
    resp2 = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "14:15",
            "end_time": "14:45",
            "reason": "Second overlapping booking"
        },
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp2.status_code == 409
    assert "already booked" in resp2.json()["detail"]


def test_invalid_doctor_returns_404():
    """6. Invalid doctor returns 404 Not Found."""
    token = make_token("user-p3", "p3@example.com", role="patient")
    monday_date = get_next_weekday_date(1)

    resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "non-existent-doctor-id",
            "appointment_date": monday_date,
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "Checkup"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_invalid_time_outside_availability():
    """7. Invalid time outside doctor's schedule returns 422 Unprocessable Entity."""
    token = make_token("user-p4", "p4@example.com", role="patient")
    sunday_date = get_next_weekday_date(0)  # Sunday (doctors only work Mon-Sat)

    # Attempt booking on Sunday
    resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": sunday_date,
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "Sunday consultation"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 422
    assert "outside doctor's active schedule" in resp.json()["detail"]


def test_patient_can_cancel_own_appointment():
    """8. Patient can cancel own appointment (200 OK)."""
    token = make_token("user-p5", "p5@example.com", role="patient")
    monday_date = get_next_weekday_date(1)

    create_resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "15:00",
            "end_time": "15:30",
            "reason": "To be cancelled"
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert create_resp.status_code == 201
    appt_id = create_resp.json()["id"]

    cancel_resp = client.patch(
        f"/api/appointments/{appt_id}/cancel",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_patient_cannot_modify_another_patients_appointment():
    """9. Patient cannot cancel/modify another patient's appointment (403 Forbidden)."""
    owner_token = make_token("owner-user", "owner@example.com", role="patient")
    intruder_token = make_token("intruder-user", "intruder@example.com", role="patient")
    monday_date = get_next_weekday_date(1)

    create_resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "16:00",
            "end_time": "16:30",
            "reason": "Owner appointment"
        },
        headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert create_resp.status_code == 201
    appt_id = create_resp.json()["id"]

    intruder_resp = client.patch(
        f"/api/appointments/{appt_id}/cancel",
        headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert intruder_resp.status_code == 403
    assert "Unauthorized" in intruder_resp.json()["detail"]


def test_doctor_can_retrieve_assigned_appointments():
    """10. Doctor can retrieve assigned appointments (200 OK)."""
    patient_token = make_token("patient-p6", "p6@example.com", role="patient", full_name="Patient Six")
    # Doctor profile ID matches seeded Dr. Sarah Jenkins profile
    doctor_token = make_token("doc-prof-sarah-jenkins", "dr.jenkins@careflow.ai", role="doctor", full_name="Dr. Sarah Jenkins")
    monday_date = get_next_weekday_date(1)

    # Patient books with Dr. Jenkins
    create_resp = client.post(
        "/api/appointments",
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": monday_date,
            "start_time": "13:00",
            "end_time": "13:30",
            "reason": "Cardiology consultation"
        },
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert create_resp.status_code == 201

    # Doctor retrieves assigned appointments
    doc_resp = client.get(
        "/api/appointments",
        headers={"Authorization": f"Bearer {doctor_token}"}
    )
    assert doc_resp.status_code == 200
    doc_appts = doc_resp.json()
    assert len(doc_appts) >= 1
    assert any(a["reason"] == "Cardiology consultation" for a in doc_appts)
