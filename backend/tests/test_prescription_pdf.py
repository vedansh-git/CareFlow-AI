"""
Tests for Doctor Prescription PDF Generation & Prescription Data Extraction
"""

import io
import pytest
from pypdf import PdfReader
from fastapi.testclient import TestClient
from app.main import app
from app.services.data_store import db_store
from app.core.clinical.prescription_parser import PrescriptionParser

client = TestClient(app)


@pytest.fixture
def test_setup():
    """Seeds predictable test doctor, patient, appointment, and SOAP notes."""
    # Doctor
    doc_prof_id = "doc-prof-sarah-jenkins"
    doc_id = "doc-sarah-jenkins-01"

    # Patient
    pat_prof_id = "patient-prof-alex-reed"
    pat_id = "patient-alex-reed-01"
    
    db_store.profiles[pat_prof_id] = {
        "id": pat_prof_id,
        "full_name": "Alex Reed",
        "role": "patient",
        "email": "alex.reed@example.com",
        "date_of_birth": "1990-05-15",
        "gender": "Male",
        "phone": "+1-555-0199"
    }
    db_store.patients[pat_id] = {
        "id": pat_id,
        "profile_id": pat_prof_id,
        "created_at": "2026-01-01T00:00:00"
    }

    # Approved Clinical Note
    note1 = db_store.create_clinical_note(
        doctor_id=doc_id,
        patient_id=pat_id,
        transcript="Doctor: Good morning Alex. Patient: I have had a severe throat infection and fever for 3 days.",
        subjective="Sore throat x 3 days, intermittent fever up to 101 F, difficulty swallowing.",
        objective="BP: 120/80 mmHg, Pulse: 78 bpm, Temp: 100.4 F, SpO2: 98%, Wt: 72 kg. Throat erythematous with tonsillar exudates.",
        assessment="Acute Streptococcal Pharyngitis with moderate pyrexia",
        plan="1. Tab. Amoxicillin-Clavulanate 625mg - 1 tablet twice daily after food for 7 days\n2. Tab. Paracetamol 650mg - 1 tablet three times daily after food for 3 days\n3. Syp. Diphenhydramine Cough Formula 100ml - 10ml at bedtime for 5 days\nInvestigations: Complete Blood Count (CBC), Throat Swab Culture\nAdvice: Warm salt water gargles 3 times daily, stay well hydrated, rest for 48 hours\nFollow up in 5 days or SOS if breathing difficulty occurs",
        status="approved"
    )

    # Draft Clinical Note
    note_draft = db_store.create_clinical_note(
        doctor_id=doc_id,
        patient_id=pat_id,
        transcript="Draft consultation transcript.",
        subjective="Mild headache",
        objective="BP: 118/76 mmHg",
        assessment="Tension Headache",
        plan="Tab. Ibuprofen 400mg - 1 tablet as needed",
        status="draft"
    )

    # Note with incomplete medication details
    note_incomplete = db_store.create_clinical_note(
        doctor_id=doc_id,
        patient_id=pat_id,
        transcript="Consultation note with minimal plan details.",
        subjective="Cough",
        objective="Chest clear",
        assessment="Acute Bronchitis",
        plan="1. Azithromycin 500mg\n2. Cough syrup",
        status="approved"
    )

    yield {
        "doc_prof_id": doc_prof_id,
        "doc_id": doc_id,
        "pat_prof_id": pat_prof_id,
        "pat_id": pat_id,
        "approved_note_id": note1["id"],
        "draft_note_id": note_draft["id"],
        "incomplete_note_id": note_incomplete["id"]
    }


@pytest.fixture
def doctor_auth_override(test_setup):
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-doctor-token"
        
    def mock_doctor_user():
        return {
            "id": test_setup["doc_prof_id"],
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
def patient_auth_override(test_setup):
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-patient-token"
        
    def mock_patient_user():
        return {
            "id": test_setup["pat_prof_id"],
            "email": "alex.reed@example.com",
            "full_name": "Alex Reed",
            "app_role": "patient"
        }
        
    app.dependency_overrides[get_current_user] = mock_patient_user
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)


@pytest.fixture
def unauthorized_patient_auth_override():
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-other-patient-token"
        
    def mock_other_patient():
        return {
            "id": "patient-prof-other-user",
            "email": "other@example.com",
            "full_name": "Other Patient",
            "app_role": "patient"
        }
        
    app.dependency_overrides[get_current_user] = mock_other_patient
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)


# ============================================================
# 1. PARSER UNIT TESTS
# ============================================================

def test_prescription_parser_vitals():
    obj_text = "Vitals: BP: 130/85 mmHg, Pulse: 82 bpm, Temp: 99.2 F, SpO2: 97%, Weight: 68 kg"
    vitals = PrescriptionParser.parse_vitals(obj_text)
    assert vitals.get("BP") == "130/85 mmHg"
    assert vitals.get("Pulse") == "82 bpm"
    assert vitals.get("Temp") == "99.2 °F"
    assert vitals.get("SpO2") == "97%"
    assert vitals.get("Weight") == "68 kg"


def test_prescription_parser_medications_complete():
    plan_text = """1. Tab. Amoxicillin 500mg - 1 tablet twice daily after food for 5 days
2. Tab. Pantoprazole 400mg - 1 tab before meals for 7 days
Investigations: Complete Blood Count (CBC)
Advice: Drink plenty of water, avoid spicy food
Follow up in 5 days"""
    parsed = PrescriptionParser.parse_plan_section(plan_text)
    assert len(parsed["medications"]) >= 2
    med1 = parsed["medications"][0]
    assert "Amoxicillin" in med1.name
    assert med1.strength == "500mg"
    assert "Twice daily" in med1.frequency or "1-0-1" in med1.frequency
    assert "After food" in med1.instructions
    assert "5 days" in med1.duration
    assert med1.is_complete is True


def test_prescription_parser_medications_incomplete_flagging():
    plan_text = "1. Azithromycin 500mg\n2. Paracetamol"
    parsed = PrescriptionParser.parse_plan_section(plan_text)
    assert len(parsed["medications"]) == 2
    # Since frequency or duration was not stated in raw text, it should flag for review
    assert parsed["medications"][0].is_complete is False
    assert parsed["medications"][0].flag_reason is not None


def test_clean_chief_complaint_removes_fluff():
    raw_subj = (
        "Doctor: Hello Alex. Patient: I have had high grade fever for 4 days with chills, "
        "productive cough with yellowish sputum, and sore throat. Patient denies shortness of breath, "
        "denies chest pain, no history of travel, no known sick contacts."
    )
    cleaned = PrescriptionParser.clean_chief_complaint(raw_subj)
    assert "Doctor:" not in cleaned
    assert "Patient:" not in cleaned
    assert "fever for 4 days" in cleaned.lower() or "fever" in cleaned.lower()
    assert "cough" in cleaned.lower()
    assert len(cleaned) < 140


def test_clean_diagnosis_removes_differentials_and_fluff():
    raw_assess = (
        "Assessment: Acute Streptococcal Pharyngitis with moderate pyrexia. "
        "Differential diagnosis includes viral upper respiratory infection, infectious mononucleosis. "
        "Plan includes throat swab culture and antipyretics."
    )
    cleaned = PrescriptionParser.clean_diagnosis(raw_assess)
    assert "Assessment:" not in cleaned
    assert "Acute Streptococcal Pharyngitis" in cleaned
    assert "Differential diagnosis" not in cleaned
    assert "Plan includes" not in cleaned
    assert len(cleaned) < 120



# ============================================================
# 2. PDF GENERATION API & SINGLE-PAGE VALIDATION TESTS
# ============================================================

def test_download_prescription_pdf_doctor_success(test_setup, doctor_auth_override):
    note_id = test_setup["approved_note_id"]
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")

    # Verify single-page PDF structure using pypdf
    pdf_reader = PdfReader(io.BytesIO(response.content))
    assert len(pdf_reader.pages) == 1

    # Verify text content on the page
    page_text = pdf_reader.pages[0].extract_text()
    assert "Dr. Sarah Jenkins" in page_text
    assert "Alex Reed" in page_text
    assert "Amoxicillin" in page_text
    assert "Acute Streptococcal Pharyngitis" in page_text
    assert "Page 1 of 1" in page_text


def test_download_prescription_pdf_patient_success(test_setup, patient_auth_override):
    note_id = test_setup["approved_note_id"]
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert len(response.content) > 1000

    pdf_reader = PdfReader(io.BytesIO(response.content))
    assert len(pdf_reader.pages) == 1


def test_download_prescription_pdf_patient_draft_forbidden(test_setup, patient_auth_override):
    # Patients cannot download draft unapproved prescriptions
    draft_note_id = test_setup["draft_note_id"]
    response = client.get(f"/api/clinical-notes/{draft_note_id}/prescription-pdf")
    assert response.status_code == 403
    assert "only available after official physician review" in response.json()["detail"]


def test_download_prescription_pdf_unauthorized_patient(test_setup, unauthorized_patient_auth_override):
    # Other patients cannot access someone else's prescription
    note_id = test_setup["approved_note_id"]
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-pdf")
    assert response.status_code == 403
    assert "cannot access prescription for another patient" in response.json()["detail"]


def test_download_prescription_pdf_not_found(doctor_auth_override):
    response = client.get("/api/clinical-notes/00000000-0000-0000-0000-000000000000/prescription-pdf")
    assert response.status_code == 404


def test_get_prescription_data_endpoint(test_setup, doctor_auth_override):
    note_id = test_setup["approved_note_id"]
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-data")
    assert response.status_code == 200
    data = response.json()
    assert data["patient_name"] == "Alex Reed"
    assert data["doctor_name"] == "Dr. Sarah Jenkins"
    assert "Amoxicillin" in data["medications"][0]["name"]
    assert data["vital_signs"]["BP"] == "120/80 mmHg"
    assert len(data["investigations"]) >= 1


def test_download_prescription_long_medication_list_single_page(test_setup, doctor_auth_override):
    # Test a heavy 8-item medication plan to ensure single-page constraint holds
    long_plan = """1. Tab. Amoxicillin 500mg - 1 tablet three times daily for 7 days
2. Tab. Paracetamol 650mg - 1 tablet twice daily for 5 days
3. Tab. Cetirizine 10mg - 1 tablet at night for 10 days
4. Syp. Ambroxol 15ml - 5ml three times daily for 5 days
5. Tab. Pantoprazole 40mg - 1 tablet before breakfast for 14 days
6. Cap. Vitamin D3 60k - 1 capsule once weekly for 8 weeks
7. Tab. Calcium Carbonate 500mg - 1 tablet daily after food for 30 days
8. Inhaler Salbutamol 100mcg - 2 puffs SOS when breathless
Investigations: Complete Blood Count, Liver Function Test, Serum Creatinine
Advice: Warm saline gargles, avoid cold drinks, deep breathing exercises
Follow up in 7 days or SOS"""
    long_note = db_store.create_clinical_note(
        doctor_id=test_setup["doc_id"],
        patient_id=test_setup["pat_id"],
        transcript="Extended prescription consultation.",
        subjective="Multiple chronic complaints, seasonal allergies.",
        objective="BP: 125/82 mmHg, Pulse: 74 bpm, Temp: 98.4 F, SpO2: 99%, Weight: 70 kg",
        assessment="Multi-symptom upper respiratory and seasonal allergy flare",
        plan=long_plan,
        status="approved"
    )

    response = client.get(f"/api/clinical-notes/{long_note['id']}/prescription-pdf")
    assert response.status_code == 200
    pdf_reader = PdfReader(io.BytesIO(response.content))
    # Must strictly fit on 1 page
    assert len(pdf_reader.pages) == 1
    page_text = pdf_reader.pages[0].extract_text()
    assert "Amoxicillin" in page_text
    assert "Salbutamol" in page_text
    assert "Page 1 of 1" in page_text


def test_download_prescription_incomplete_fields_flagged(test_setup, doctor_auth_override):
    note_id = test_setup["incomplete_note_id"]
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-pdf")
    assert response.status_code == 200
    pdf_reader = PdfReader(io.BytesIO(response.content))
    assert len(pdf_reader.pages) == 1

    # Check that prescription data flagged missing attributes
    data_res = client.get(f"/api/clinical-notes/{note_id}/prescription-data")
    assert data_res.status_code == 200
    data = data_res.json()
    assert data["missing_fields_flag"] is True
    assert any("verify with doctor" in m.get("flag_reason", "") for m in data["medications"])


def test_download_prescription_other_doctor_forbidden(test_setup):
    from app.core.security import get_current_user, security_scheme
    
    class MockCredentials:
        credentials = "fake-other-doc-token"
        
    def mock_other_doctor():
        return {
            "id": "doc-prof-marcus-vance",
            "email": "dr.vance@careflow.ai",
            "full_name": "Dr. Marcus Vance",
            "app_role": "doctor"
        }
        
    app.dependency_overrides[get_current_user] = mock_other_doctor
    app.dependency_overrides[security_scheme] = lambda: MockCredentials()
    
    note_id = test_setup["approved_note_id"]  # authored by Dr. Sarah Jenkins
    response = client.get(f"/api/clinical-notes/{note_id}/prescription-pdf")
    
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(security_scheme, None)

    assert response.status_code == 403
    assert "Unauthorized" in response.json()["detail"]

