import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.services.data_store import db_store
from app.core.agent.tools import execute_tool

client = TestClient(app)

MOCK_PATIENT_USER = {
    "id": "test-patient-user-bidhan-001",
    "email": "patient@careflow.ai",
    "full_name": "Test Patient",
    "app_role": "patient",
}

# Sample dynamic Supabase doctor payload representing a newly registered doctor
MOCK_SUPABASE_BIDHAN_DOCTOR = {
    "id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
    "profile_id": "prof-bidhan-roy-9999",
    "specialty": "General Medicine",
    "qualification": "MD",
    "bio": "Consultant Physician with extensive clinical experience in General Medicine.",
    "is_active": True,
    "consultation_fee": 90.0,
    "profiles": {
        "id": "prof-bidhan-roy-9999",
        "full_name": "Dr. Bidhan Chandra Roy",
        "role": "doctor",
        "phone": "+1-555-0199",
        "email": "dr.bidhan@careflow.ai",
    },
}

MOCK_SUPABASE_CARDIOLOGIST = {
    "id": "c1c2c3c4-c5c6-47c8-c9c0-998877665544",
    "profile_id": "prof-ananya-sen-8888",
    "specialty": "Cardiology",
    "qualification": "MD, DM - Cardiology",
    "bio": "Senior Interventional Cardiologist specializing in preventive heart health.",
    "is_active": True,
    "consultation_fee": 160.0,
    "profiles": {
        "id": "prof-ananya-sen-8888",
        "full_name": "Dr. Ananya Sen",
        "role": "doctor",
        "phone": "+1-555-0188",
        "email": "dr.sen@careflow.ai",
    },
}


@pytest.fixture(autouse=True)
def reset_store():
    db_store.seed_initial_data()
    yield
    db_store.seed_initial_data()


# ==============================================================================
# 1. TEST DYNAMIC DOCTOR DISCOVERY VIA SUPABASE
# ==============================================================================

def test_search_doctor_by_name_discovers_newly_registered_doctor():
    """A. Test that search_doctors(name='Bidhan Chandra Roy') discovers a live Supabase doctor."""
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [MOCK_SUPABASE_BIDHAN_DOCTOR]
        mock_get.return_value = mock_response

        res = execute_tool("search_doctors", {"name": "Bidhan Chandra Roy"}, MOCK_PATIENT_USER)
        assert res["count"] >= 1
        found_names = [d["full_name"] for d in res["doctors"]]
        assert "Dr. Bidhan Chandra Roy" in found_names
        
        # Verify doctor ID is the real Supabase UUID
        bidhan_doc = next(d for d in res["doctors"] if "Bidhan" in d["full_name"])
        assert bidhan_doc["id"] == "a1b2c3d4-e5f6-47a8-b9c0-112233445566"
        assert bidhan_doc["specialty"] == "General Medicine"


def test_search_doctor_by_specialty():
    """B. Test that search_doctors(specialty='Cardiology') discovers doctors from Supabase."""
    with patch("httpx.Client.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [MOCK_SUPABASE_CARDIOLOGIST]
        mock_get.return_value = mock_response

        res = execute_tool("search_doctors", {"specialty": "Cardiology"}, MOCK_PATIENT_USER)
        assert res["count"] >= 1
        found_names = [d["full_name"] for d in res["doctors"]]
        assert "Dr. Ananya Sen" in found_names
        sen_doc = next(d for d in res["doctors"] if "Ananya" in d["full_name"])
        assert sen_doc["id"] == "c1c2c3c4-c5c6-47c8-c9c0-998877665544"


def test_get_doctor_details_using_supabase_uuid():
    """C. Test get_doctor_details retrieves full profile using Supabase UUID."""
    with patch("httpx.Client.get") as mock_get:
        def side_effect(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            if "doctor_availability" in url:
                resp.json.return_value = [
                    {
                        "id": "slot-uuid-001",
                        "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                        "day_of_week": 1,
                        "start_time": "09:00:00",
                        "end_time": "17:00:00",
                        "is_active": True,
                    }
                ]
            else:
                resp.json.return_value = [MOCK_SUPABASE_BIDHAN_DOCTOR]
            return resp

        mock_get.side_effect = side_effect

        res = execute_tool("get_doctor_details", {"doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566"}, MOCK_PATIENT_USER)
        assert "doctor" in res
        assert res["doctor"]["full_name"] == "Dr. Bidhan Chandra Roy"
        assert res["doctor"]["id"] == "a1b2c3d4-e5f6-47a8-b9c0-112233445566"
        assert len(res["weekly_schedule"]) >= 1


def test_get_doctor_availability_for_supabase_doctor():
    """D. Test check_doctor_availability computes 30-min slots for a Supabase doctor."""
    with patch("httpx.Client.get") as mock_get:
        def side_effect(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            if "doctor_availability" in url:
                resp.json.return_value = [
                    {
                        "id": "slot-uuid-001",
                        "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                        "day_of_week": 1,
                        "start_time": "09:00:00",
                        "end_time": "17:00:00",
                        "is_active": True,
                    }
                ]
            elif "appointments" in url:
                resp.json.return_value = []
            else:
                resp.json.return_value = [MOCK_SUPABASE_BIDHAN_DOCTOR]
            return resp

        mock_get.side_effect = side_effect

        # 2026-10-05 is a Monday (day_of_week=1)
        res = execute_tool(
            "check_doctor_availability",
            {
                "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                "appointment_date": "2026-10-05",
            },
            MOCK_PATIENT_USER,
        )
        assert "available_slots" in res
        assert res["total_available"] > 0
        slot_starts = [s["start_time"] for s in res["available_slots"]]
        assert "09:00" in slot_starts
        assert "09:30" in slot_starts


def test_prepare_confirmation_and_booking_with_supabase_doctor_uuid():
    """E. Test that prepare_booking_confirmation and book_appointment create appointment using real Supabase doctor UUID."""
    with patch("httpx.Client.get") as mock_get, patch("httpx.Client.post") as mock_post:
        def get_side_effect(url, headers=None):
            resp = MagicMock()
            resp.status_code = 200
            if "doctor_availability" in url:
                resp.json.return_value = [
                    {
                        "id": "slot-uuid-001",
                        "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                        "day_of_week": 1,
                        "start_time": "09:00:00",
                        "end_time": "17:00:00",
                        "is_active": True,
                    }
                ]
            elif "appointments" in url:
                resp.json.return_value = []
            elif "patients" in url:
                resp.json.return_value = [{"id": "patient-uuid-bidhan-01", "profile_id": MOCK_PATIENT_USER["id"]}]
            else:
                resp.json.return_value = [MOCK_SUPABASE_BIDHAN_DOCTOR]
            return resp

        mock_get.side_effect = get_side_effect

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = [{
            "id": "appt-uuid-9999",
            "patient_id": "patient-uuid-bidhan-01",
            "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
            "appointment_date": "2026-10-05",
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "[IN_PERSON] Routine Checkup",
            "status": "scheduled",
            "created_at": "2026-10-05T00:00:00Z",
            "updated_at": "2026-10-05T00:00:00Z",
        }]
        mock_post.return_value = mock_post_resp

        # 1. Prepare confirmation
        conf_res = execute_tool(
            "prepare_booking_confirmation",
            {
                "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                "appointment_date": "2026-10-05",
                "appointment_time": "10:00",
                "consultation_type": "in_person",
                "notes": "Routine Checkup",
            },
            MOCK_PATIENT_USER,
        )
        assert conf_res["status"] == "ready_for_confirmation"
        assert conf_res["confirmation_details"]["doctor_id"] == "a1b2c3d4-e5f6-47a8-b9c0-112233445566"
        assert conf_res["confirmation_details"]["doctor_name"] == "Dr. Bidhan Chandra Roy"

        # 2. Book appointment
        book_res = execute_tool(
            "book_appointment",
            {
                "doctor_id": "a1b2c3d4-e5f6-47a8-b9c0-112233445566",
                "appointment_date": "2026-10-05",
                "appointment_time": "10:00",
                "consultation_type": "in_person",
                "notes": "Routine Checkup",
                "confirmed": True,
            },
            MOCK_PATIENT_USER,
        )
        assert book_res["status"] == "booking_success"
        assert book_res["appointment"]["doctor_id"] == "a1b2c3d4-e5f6-47a8-b9c0-112233445566"


def test_fallback_to_in_memory_when_supabase_unavailable():
    """F. Test that if Supabase throws connection error, fallback to in-memory seed doctors works."""
    with patch("httpx.Client.get", side_effect=Exception("Supabase connection timeout")):
        res = execute_tool("search_doctors", {"name": "Jenkins"}, MOCK_PATIENT_USER)
        assert res["count"] >= 1
        assert any("Jenkins" in d["full_name"] for d in res["doctors"])
        
        details = execute_tool("get_doctor_details", {"doctor_id": "doc-sarah-jenkins-01"}, MOCK_PATIENT_USER)
        assert "doctor" in details
        assert details["doctor"]["full_name"] == "Dr. Sarah Jenkins"
