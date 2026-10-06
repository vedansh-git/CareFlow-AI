import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import get_current_user
from app.services.data_store import db_store
from app.core.agent.tools import execute_tool, AGENT_TOOLS_SCHEMA, _compute_available_slots
from app.core.agent.groq_provider import GroqProvider, GroqProviderError
from app.core.agent.appointment_agent import AppointmentAgent


client = TestClient(app)

MOCK_PATIENT_USER = {
    "id": "test-patient-user-001",
    "email": "patient@careflow.ai",
    "full_name": "Test Patient",
    "app_role": "patient",
}

MOCK_AUTH_HEADERS = {
    "Authorization": "Bearer mock-test-token"
}


@pytest.fixture(autouse=True)
def reset_store():
    """Reset data store and dependency overrides before each test."""
    db_store.seed_initial_data()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


# ==============================================================================
# 1. TEST AGENT TOOL EXECUTION
# ==============================================================================

def test_tool_search_doctors():
    # 1. Search by specialty
    res = execute_tool("search_doctors", {"specialty": "Cardiology"}, MOCK_PATIENT_USER)
    assert res["count"] >= 1
    assert any("Jenkins" in d["full_name"] for d in res["doctors"])
    assert res["doctors"][0]["clinic_address"] is not None

    # 2. Search by name
    res2 = execute_tool("search_doctors", {"name": "Marcus"}, MOCK_PATIENT_USER)
    assert res2["count"] >= 1
    assert "Dr. Marcus Vance" in [d["full_name"] for d in res2["doctors"]]

    # 3. Search by max_fee
    res3 = execute_tool("search_doctors", {"max_fee": 130.0}, MOCK_PATIENT_USER)
    for doc in res3["doctors"]:
        if doc.get("consultation_fee") is not None:
            assert doc["consultation_fee"] <= 130.0


def test_tool_get_doctor_details():
    doc_id = "doc-sarah-jenkins-01"
    res = execute_tool("get_doctor_details", {"doctor_id": doc_id}, MOCK_PATIENT_USER)
    assert "doctor" in res
    assert res["doctor"]["full_name"] == "Dr. Sarah Jenkins"
    assert res["doctor"]["specialty"] == "Cardiology"
    assert res["doctor"]["clinic_address"] is not None
    assert "+1-555-" in res["doctor"]["contact_phone"]
    assert len(res["demo_reviews"]) >= 1
    assert res["demo_reviews"][0]["is_demo"] is True


def test_tool_check_doctor_availability():
    doc_id = "doc-sarah-jenkins-01"
    # Sarah Jenkins works Mondays (1), Wednesdays (3), Fridays (5) 09:00 - 13:00
    # 2026-10-05 is a Monday
    res = execute_tool("check_doctor_availability", {"doctor_id": doc_id, "appointment_date": "2026-10-05"}, MOCK_PATIENT_USER)
    assert "available_slots" in res
    assert res["total_available"] > 0
    slot_starts = [s["start_time"] for s in res["available_slots"]]
    assert "09:00" in slot_starts
    assert "09:30" in slot_starts


def test_tool_prepare_booking_confirmation():
    doc_id = "doc-sarah-jenkins-01"
    # 1. Valid slot on a Monday
    res = execute_tool(
        "prepare_booking_confirmation",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-05",
            "appointment_time": "09:30",
            "consultation_type": "in_person",
        },
        MOCK_PATIENT_USER,
    )
    assert res["status"] == "ready_for_confirmation"
    assert res["confirmation_details"]["doctor_name"] == "Dr. Sarah Jenkins"
    assert res["confirmation_details"]["appointment_time"] == "09:30"
    assert "instructions" in res

    # 2. Unavailable slot (Sunday)
    res_sunday = execute_tool(
        "prepare_booking_confirmation",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-04",  # Sunday
            "appointment_time": "09:30",
        },
        MOCK_PATIENT_USER,
    )
    assert res_sunday["status"] == "slot_unavailable"


def test_tool_book_appointment_requires_explicit_confirmation():
    doc_id = "doc-sarah-jenkins-01"
    # Unconfirmed booking attempt MUST be rejected
    res_unconfirmed = execute_tool(
        "book_appointment",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-05",
            "appointment_time": "10:00",
            "confirmed": False,
        },
        MOCK_PATIENT_USER,
    )
    assert res_unconfirmed["status"] == "confirmation_required"
    assert "error" in res_unconfirmed

    # Confirmed booking attempt succeeds
    res_confirmed = execute_tool(
        "book_appointment",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-05",
            "appointment_time": "10:00",
            "confirmed": True,
        },
        MOCK_PATIENT_USER,
    )
    assert res_confirmed["status"] == "booking_success"
    assert "appointment" in res_confirmed
    assert res_confirmed["appointment"]["doctor_id"] == doc_id
    assert res_confirmed["appointment"]["appointment_date"] == "2026-10-05"


def test_tool_appointment_conflict_prevention():
    doc_id = "doc-sarah-jenkins-01"
    # 1. Book initial slot
    execute_tool(
        "book_appointment",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-05",
            "appointment_time": "11:00",
            "confirmed": True,
        },
        MOCK_PATIENT_USER,
    )

    # 2. Availability should now NOT include 11:00
    avail = _compute_available_slots(doc_id, "2026-10-05")
    slot_starts = [s["start_time"] for s in avail["available_slots"]]
    assert "11:00" not in slot_starts

    # 3. Attempting to book the exact same slot again raises conflict
    second_user = {
        "id": "second-patient-user",
        "email": "other@patient.com",
        "full_name": "Other Patient",
        "app_role": "patient",
    }
    conflict_res = execute_tool(
        "book_appointment",
        {
            "doctor_id": doc_id,
            "appointment_date": "2026-10-05",
            "appointment_time": "11:00",
            "confirmed": True,
        },
        second_user,
    )
    assert "error" in conflict_res
    assert "already booked" in conflict_res["error"] or "409" in conflict_res["error"]


# ==============================================================================
# 2. TEST GROQ PROVIDER & FALLBACK LOGIC
# ==============================================================================

@pytest.mark.anyio
async def test_groq_provider_fallback_chain():
    provider = GroqProvider()
    provider.api_key = "test-groq-key"

    # Mock responses: Primary model hits 429 (Rate Limit), Fallback model succeeds
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    mock_resp_429.json.return_value = {"error": {"message": "Rate limit reached", "type": "rate_limit_exceeded"}}
    mock_resp_429.text = "Rate limit reached"

    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Dr. Sarah Jenkins is available on Monday at 09:00 AM.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 120},
    }

    with patch("httpx.AsyncClient.post", side_effect=[mock_resp_429, mock_resp_200]):
        result = await provider.chat_completion(
            messages=[{"role": "user", "content": "When is Dr. Sarah Jenkins free?"}]
        )

        assert result["fallback_used"] is True
        assert result["model_used"] == "openai/gpt-oss-20b"
        assert "Sarah Jenkins" in result["message"]["content"]
        assert len(result["attempted_models"]) == 2


@pytest.mark.anyio
async def test_groq_provider_unconfigured_error():
    provider = GroqProvider()
    with patch.object(GroqProvider, "api_key", ""):
        with pytest.raises(GroqProviderError) as exc_info:
            await provider.chat_completion(messages=[{"role": "user", "content": "Hello"}])
        assert exc_info.value.status_code == 401
        assert "not configured" in str(exc_info.value)


# ==============================================================================
# 3. TEST AGENT MULTI-TURN TOOL CALLING ORCHESTRATOR
# ==============================================================================

@pytest.mark.anyio
async def test_appointment_agent_multi_turn_flow():
    agent = AppointmentAgent()

    # Step 1: Groq requests tool call `search_doctors`
    mock_tool_call_resp = {
        "message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "search_doctors",
                        "arguments": '{"specialty": "Cardiology"}',
                    },
                }
            ],
        },
        "finish_reason": "tool_calls",
        "model_used": "openai/gpt-oss-120b",
        "fallback_used": False,
        "attempted_models": ["openai/gpt-oss-120b"],
    }

    # Step 2: Groq responds with final answer after seeing tool output
    mock_final_resp = {
        "message": {
            "role": "assistant",
            "content": "I found Dr. Sarah Jenkins specializing in Cardiology at CareFlow Heart & Vascular Pavilion.",
            "tool_calls": None,
        },
        "finish_reason": "stop",
        "model_used": "openai/gpt-oss-120b",
        "fallback_used": False,
        "attempted_models": ["openai/gpt-oss-120b"],
    }

    with patch.object(agent.groq, "chat_completion", side_effect=[mock_tool_call_resp, mock_final_resp]):
        res = await agent.run(
            conversation_history=[{"role": "user", "content": "Find me a cardiologist."}],
            current_user=MOCK_PATIENT_USER,
        )

        assert "Dr. Sarah Jenkins" in res["content"]
        assert len(res["tool_calls_executed"]) == 1
        assert res["tool_calls_executed"][0]["tool"] == "search_doctors"
        assert res["metadata"]["provider"] == "Groq"


# ==============================================================================
# 4. TEST AGENT API ENDPOINT & INDEPENDENT MANUAL BOOKING
# ==============================================================================

def test_agent_api_unauthenticated_fails():
    resp = client.post("/api/agent/appointment-chat", json={"messages": [{"role": "user", "content": "Hello"}]})
    assert resp.status_code == 401


def test_agent_api_authenticated_chat():
    mock_agent_result = {
        "content": "Dr. Sarah Jenkins is available on Monday at 09:00 AM. Would you like to confirm this slot?",
        "tool_calls_executed": [
            {
                "id": "call_abc",
                "tool": "check_doctor_availability",
                "arguments": {"doctor_id": "doc-sarah-jenkins-01", "appointment_date": "2026-10-05"},
                "output": {"total_available": 6},
            }
        ],
        "pending_confirmation": {
            "doctor_id": "doc-sarah-jenkins-01",
            "doctor_name": "Dr. Sarah Jenkins",
            "specialty": "Cardiology",
            "appointment_date": "2026-10-05",
            "appointment_time": "09:00",
            "consultation_fee": 150.0,
        },
        "booking_result": None,
        "metadata": {
            "provider": "Groq",
            "model_used": "openai/gpt-oss-120b",
            "fallback_used": False,
        },
    }

    app.dependency_overrides[get_current_user] = lambda: MOCK_PATIENT_USER
    with patch("app.api.agent.appointment_agent.run", AsyncMock(return_value=mock_agent_result)):
        resp = client.post(
            "/api/agent/appointment-chat",
            headers=MOCK_AUTH_HEADERS,
            json={"messages": [{"role": "user", "content": "Check availability for Dr. Sarah Jenkins on Monday"}]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "Dr. Sarah Jenkins" in data["content"]
        assert data["pending_confirmation"]["doctor_id"] == "doc-sarah-jenkins-01"
        assert data["metadata"]["provider"] == "Groq"


def test_manual_booking_independent_of_groq():
    """Verify that manual booking endpoint operates seamlessly without requiring Groq."""
    app.dependency_overrides[get_current_user] = lambda: MOCK_PATIENT_USER
    resp = client.post(
        "/api/appointments",
        headers=MOCK_AUTH_HEADERS,
        json={
            "doctor_id": "doc-sarah-jenkins-01",
            "appointment_date": "2026-10-05",
            "start_time": "09:00",
            "end_time": "09:30",
            "reason": "Manual Routine Checkup",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["doctor_id"] == "doc-sarah-jenkins-01"
    assert data["appointment_date"] == "2026-10-05"
    assert data["status"] in ["scheduled", "confirmed"]
