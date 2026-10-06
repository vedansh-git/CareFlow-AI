import io
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.llm.provider import (
    LLMProviderError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError
)
from app.services.data_store import db_store

client = TestClient(app)


# Mock auth overrides
@pytest.fixture
def doctor_auth_override():
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-doctor-token"
        
    def mock_doctor_user():
        return {
            "id": "doc-prof-sarah-jenkins",
            "email": "dr.jenkins@careflow.ai",
            "full_name": "Dr. Sarah Jenkins",
            "app_role": "doctor"
        }
        
    app.dependency_overrides[get_current_user] = mock_doctor_user
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)


@pytest.fixture
def patient_auth_override():
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-patient-token"
        
    def mock_patient_user():
        return {
            "id": "patient-prof-alex-reed",
            "email": "alex.reed@example.com",
            "full_name": "Alex Reed",
            "app_role": "patient"
        }
        
    app.dependency_overrides[get_current_user] = mock_patient_user
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)


# 1. Role-Based Access Control Tests
def test_clinical_notes_patient_cannot_transcribe(patient_auth_override):
    fake_audio = io.BytesIO(b"dummy audio data")
    response = client.post(
        "/api/clinical-notes/transcribe",
        files={"file": ("recording.webm", fake_audio, "audio/webm")}
    )
    assert response.status_code == 403
    assert "Doctor account" in response.json()["detail"]


def test_clinical_notes_patient_cannot_generate_soap(patient_auth_override):
    response = client.post(
        "/api/clinical-notes/generate-soap",
        json={"transcript": "Patient reported fever."}
    )
    assert response.status_code == 403
    assert "Doctor account" in response.json()["detail"]


def test_clinical_notes_patient_cannot_create_note(patient_auth_override):
    response = client.post(
        "/api/clinical-notes",
        json={
            "patient_id": "patient-1",
            "transcript": "Patient reported fever."
        }
    )
    assert response.status_code == 403


# 2. Audio Transcription Tests
def test_transcribe_audio_empty_file(doctor_auth_override):
    empty_audio = io.BytesIO(b"")
    response = client.post(
        "/api/clinical-notes/transcribe",
        files={"file": ("recording.webm", empty_audio, "audio/webm")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_transcribe_audio_invalid_extension(doctor_auth_override):
    fake_file = io.BytesIO(b"plain text content")
    response = client.post(
        "/api/clinical-notes/transcribe",
        files={"file": ("document.txt", fake_file, "text/plain")}
    )
    assert response.status_code == 400
    assert "unsupported audio format" in response.json()["detail"].lower()


def test_transcribe_audio_mock_success(doctor_auth_override):
    fake_audio = io.BytesIO(b"RIFF....WAVEfmt ....data....")
    
    with patch("app.core.audio.transcription_service.AudioTranscriptionService._run_transcription") as mock_stt:
        mock_stt.return_value = {
            "transcript": "Patient complains of persistent headache for three days.",
            "language": "en",
            "duration": 5.2
        }
        
        response = client.post(
            "/api/clinical-notes/transcribe",
            files={"file": ("consultation.wav", fake_audio, "audio/wav")}
        )
        assert response.status_code == 200
        data = response.json()
        assert "persistent headache" in data["transcript"]
        assert data["language"] == "en"
        assert data["duration"] == 5.2


# 3. SOAP Note Generation Tests
def test_generate_soap_empty_transcript(doctor_auth_override):
    response = client.post(
        "/api/clinical-notes/generate-soap",
        json={"transcript": ""}
    )
    assert response.status_code == 422


def test_generate_soap_mock_success(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    mock_llm = MagicMock()
    
    mock_llm.generate_response = AsyncMock(return_value="""{
        "subjective": "Patient reports 3 days of mild fever and dry cough.",
        "objective": "Temperature 100.2 F, Chest clear on auscultation.",
        "assessment": "Viral upper respiratory tract infection.",
        "plan": "Acetaminophen 500mg as needed, oral hydration, rest."
    }""")
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={
                "transcript": "Doctor: How are you? Patient: I have had a mild fever and dry cough for 3 days.",
                "patient_context": "Alex Reed, 35 y/o Male"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "mild fever" in data["subjective"]
        assert "100.2 F" in data["objective"]
        assert "Viral upper respiratory" in data["assessment"]
        assert "Acetaminophen" in data["plan"]
        assert "AI-Generated" in data["disclaimer"]
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_generate_soap_missing_information_defaults(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    mock_llm = MagicMock()
    # LLM returns only subjective findings; other sections are omitted
    mock_llm.generate_response = AsyncMock(return_value="""{
        "subjective": "Patient reported knee soreness after jogging.",
        "objective": "Not documented",
        "assessment": "Not documented",
        "plan": "Not documented"
    }""")
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "My knee hurts after jogging."}
        )
        assert response.status_code == 200
        data = response.json()
        assert "knee soreness" in data["subjective"]
        assert data["objective"] == "Not documented"
        assert data["assessment"] == "Not documented"
        assert data["plan"] == "Not documented"
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_generate_soap_rate_limit_429(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    mock_llm = MagicMock()
    mock_llm.generate_response = AsyncMock(side_effect=LLMRateLimitError("Gemini rate limit exceeded"))
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "Checkup consultation."}
        )
        assert response.status_code == 429
        assert "rate limit" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_generate_soap_with_model_attribution_primary(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    from app.core.llm.provider import GenerationResult
    mock_llm = MagicMock()
    mock_llm.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text='{"subjective": "Headache", "objective": "BP normal", "assessment": "Tension headache", "plan": "Rest"}',
            model="gemini-3.8-flash",
            provider="Google Gemini",
            fallback_used=False,
            attempted_models=["gemini-3.8-flash"]
        )
    )
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "Doctor: Any pain? Patient: Headache."}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["subjective"] == "Headache"
        assert "model_attribution" in data
        assert data["model_attribution"]["model"] == "gemini-3.8-flash"
        assert data["model_attribution"]["provider"] == "Google Gemini"
        assert data["model_attribution"]["fallback_used"] is False
        assert data["model_attribution"]["attempted_models"] == ["gemini-3.8-flash"]
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_generate_soap_with_model_attribution_fallback(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    from app.core.llm.provider import GenerationResult
    mock_llm = MagicMock()
    mock_llm.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text='{"subjective": "Fever", "objective": "101 F", "assessment": "Flu", "plan": "Fluids"}',
            model="gemini-3.7-flash",
            provider="Google Gemini",
            fallback_used=True,
            attempted_models=["gemini-3.8-flash", "gemini-3.7-flash"]
        )
    )
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "Patient with fever."}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["subjective"] == "Fever"
        assert "model_attribution" in data
        assert data["model_attribution"]["model"] == "gemini-3.7-flash"
        assert data["model_attribution"]["fallback_used"] is True
        assert data["model_attribution"]["attempted_models"] == ["gemini-3.8-flash", "gemini-3.7-flash"]
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


def test_generate_soap_gemini_503_groq_fallback(doctor_auth_override):
    """Verify SOAP generation when Gemini hits 503 and Groq fallback generates valid SOAP."""
    from app.api.clinical_notes import get_llm_provider
    from app.core.llm.provider import FallbackLLMProvider, GenerationResult, LLMServiceUnavailableError
    
    mock_gemini = MagicMock()
    mock_gemini.model = "gemini-3.8-flash"
    mock_gemini.generate_response_with_metadata = AsyncMock(
        side_effect=LLMServiceUnavailableError("Gemini model 'gemini-flash-latest' is currently experiencing high demand (HTTP 503).")
    )
    
    mock_groq = MagicMock()
    mock_groq.generate_response_with_metadata = AsyncMock(
        return_value=GenerationResult(
            text='{"subjective": "Patient reports severe migraine.", "objective": "BP 125/82", "assessment": "Migraine headache", "plan": "Sumatriptan 50mg"}',
            model="openai/gpt-oss-120b",
            provider="Groq",
            fallback_used=True,
            attempted_models=["openai/gpt-oss-120b"]
        )
    )
    
    fallback_router = FallbackLLMProvider(primary=mock_gemini, fallback=mock_groq)
    app.dependency_overrides[get_llm_provider] = lambda: fallback_router
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "Patient: I have a severe migraine. Doctor: Let's check BP, 125/82. I will prescribe Sumatriptan 50mg."}
        )
        assert response.status_code == 200
        data = response.json()
        assert "migraine" in data["subjective"].lower()
        assert "125/82" in data["objective"]
        assert "Migraine" in data["assessment"]
        assert "Sumatriptan" in data["plan"]
        assert data["model_attribution"]["provider"] == "Groq"
        assert data["model_attribution"]["fallback_used"] is True
        
        mock_gemini.generate_response_with_metadata.assert_called_once()
        mock_groq.generate_response_with_metadata.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)




def test_generate_soap_timeout_504(doctor_auth_override):
    from app.api.clinical_notes import get_llm_provider
    mock_llm = MagicMock()
    mock_llm.generate_response = AsyncMock(side_effect=LLMTimeoutError("Request timed out"))
    
    app.dependency_overrides[get_llm_provider] = lambda: mock_llm
    
    try:
        response = client.post(
            "/api/clinical-notes/generate-soap",
            json={"transcript": "Checkup consultation."}
        )
        assert response.status_code == 504
        assert "timed out" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_llm_provider, None)


# 4. Clinical Note Persistence, Editing, and Approval Tests
def test_clinical_note_lifecycle_and_authorization(doctor_auth_override):
    # Create patient record in store
    patient = db_store.get_or_create_patient(profile_id="patient-prof-alex-reed", full_name="Alex Reed")
    
    # Step A: Doctor creates a draft clinical note
    create_payload = {
        "patient_id": patient["id"],
        "transcript": "Doctor: Blood pressure 120/80. Patient: Feeling fine.",
        "subjective": "Patient reports feeling well.",
        "objective": "BP 120/80 mmHg.",
        "assessment": "Routine wellness exam normal.",
        "plan": "Follow up in 1 year.",
        "status": "draft"
    }
    create_res = client.post("/api/clinical-notes", json=create_payload)
    assert create_res.status_code == 201
    note = create_res.json()
    note_id = note["id"]
    assert note["status"] == "draft"
    assert note["reviewed_at"] is None
    
    # Step B: Doctor updates note draft sections
    update_payload = {
        "plan": "Follow up in 6 months for routine lipid check."
    }
    update_res = client.put(f"/api/clinical-notes/{note_id}", json=update_payload)
    assert update_res.status_code == 200
    updated_note = update_res.json()
    assert "6 months" in updated_note["plan"]
    assert updated_note["status"] == "draft"
    
    # Step C: Doctor approves and finalizes the note
    approve_res = client.post(f"/api/clinical-notes/{note_id}/approve")
    assert approve_res.status_code == 200
    approved_note = approve_res.json()
    assert approved_note["status"] == "approved"
    assert approved_note["reviewed_at"] is not None
    
    # Step D: List clinical notes for doctor
    list_res = client.get("/api/clinical-notes")
    assert list_res.status_code == 200
    notes_list = list_res.json()
    assert any(n["id"] == note_id for n in notes_list)


def test_doctor_cannot_modify_other_doctor_note():
    # Setup two doctor profiles in store
    doc1 = db_store.doctors["doc-sarah-jenkins-01"]
    doc2 = db_store.doctors["doc-marcus-vance-02"]
    patient = db_store.get_or_create_patient(profile_id="patient-prof-alex-reed")
    
    # Create note authored by Doc 1
    note = db_store.create_clinical_note(
        doctor_id=doc1["id"],
        patient_id=patient["id"],
        transcript="Dialogue",
        subjective="Subj",
        objective="Obj",
        assessment="Assess",
        plan="Plan"
    )
    
    # Authenticate as Doc 2 (Dr. Marcus Vance)
    from app.core.security import get_current_user, security_scheme
    
    def mock_doc2():
        return {
            "id": "doc-prof-marcus-vance",
            "email": "dr.vance@careflow.ai",
            "full_name": "Dr. Marcus Vance",
            "app_role": "doctor"
        }
        
    app.dependency_overrides[get_current_user] = mock_doc2
    app.dependency_overrides[security_scheme] = lambda: MagicMock(credentials="fake-token")
    
    try:
        # Doc 2 tries to update Doc 1's note -> 403 Forbidden
        update_res = client.put(f"/api/clinical-notes/{note['id']}", json={"plan": "Hacked Plan"})
        assert update_res.status_code == 403
        assert "another physician" in update_res.json()["detail"]
        
        # Doc 2 tries to approve Doc 1's note -> 403 Forbidden
        approve_res = client.post(f"/api/clinical-notes/{note['id']}/approve")
        assert approve_res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(security_scheme, None)


def test_doctor_cannot_document_other_doctor_appointment(doctor_auth_override):
    # Doc 1 is Dr. Sarah Jenkins ("doc-sarah-jenkins-01")
    # Create an appointment assigned to Doc 2 (Dr. Marcus Vance "doc-marcus-vance-02")
    patient = db_store.get_or_create_patient(profile_id="patient-prof-alex-reed")
    doc2_appt = db_store.create_appointment(
        patient_id=patient["id"],
        doctor_id="doc-marcus-vance-02",
        appt_date="2026-10-15",
        start_time="10:00",
        end_time="10:30",
        reason="Neurology consult"
    )
    
    # Doc 1 attempts to create a clinical note for Doc 2's appointment
    res = client.post(
        "/api/clinical-notes",
        json={
            "patient_id": patient["id"],
            "appointment_id": doc2_appt["id"],
            "transcript": "Consultation text."
        }
    )
    assert res.status_code == 403
    assert "own assigned appointments" in res.json()["detail"]


def test_doctor_can_document_own_assigned_appointment(doctor_auth_override):
    patient = db_store.get_or_create_patient(profile_id="patient-prof-alex-reed")
    # Create appointment for Doc 1 (Dr. Sarah Jenkins "doc-sarah-jenkins-01")
    doc1_appt = db_store.create_appointment(
        patient_id=patient["id"],
        doctor_id="doc-sarah-jenkins-01",
        appt_date="2026-10-16",
        start_time="11:00",
        end_time="11:30",
        reason="Cardiology follow-up"
    )
    
    res = client.post(
        "/api/clinical-notes",
        json={
            "patient_id": patient["id"],
            "appointment_id": doc1_appt["id"],
            "transcript": "Follow up consultation dialogue.",
            "subjective": "Feeling great.",
            "status": "draft"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["appointment_id"] == doc1_appt["id"]
    assert data["doctor_id"] == "doc-sarah-jenkins-01"


def test_unverified_inactive_doctor_cannot_create_note():
    # Setup inactive doctor in db_store
    inactive_prof_id = "doc-prof-inactive"
    inactive_doc_id = "doc-inactive-01"
    db_store.profiles[inactive_prof_id] = {
        "id": inactive_prof_id,
        "full_name": "Dr. Inactive",
        "role": "doctor",
        "email": "dr.inactive@careflow.ai"
    }
    db_store.doctors[inactive_doc_id] = {
        "id": inactive_doc_id,
        "profile_id": inactive_prof_id,
        "specialty": "General",
        "is_active": False  # Inactive / Unverified
    }
    
    from app.core.security import get_current_user, security_scheme
    app.dependency_overrides[get_current_user] = lambda: {
        "id": inactive_prof_id,
        "email": "dr.inactive@careflow.ai",
        "full_name": "Dr. Inactive",
        "app_role": "doctor"
    }
    app.dependency_overrides[security_scheme] = lambda: MagicMock(credentials="fake-token")
    
    try:
        res = client.post(
            "/api/clinical-notes",
            json={
                "patient_id": "patient-1",
                "transcript": "Consultation text."
            }
        )
        assert res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(security_scheme, None)

