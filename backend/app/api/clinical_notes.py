import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Response
from app.services.prescription_pdf_service import prescription_pdf_service


from app.core.security import get_current_user
from app.core.llm.provider import (
    FallbackLLMProvider,
    OpenAILikeProvider,
    LLMProviderInterface,
    LLMProviderError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMServiceUnavailableError
)
from app.core.audio.transcription_service import (
    AudioTranscriptionService,
    get_transcription_service
)
from app.core.clinical.soap_generator import SoapNoteGenerator
from app.services.clinical_notes_service import clinical_notes_service
from app.schemas.clinical_notes import (
    TranscriptionResponse,
    SoapGenerateRequest,
    SoapGenerateResponse,
    ClinicalNoteCreate,
    ClinicalNoteUpdate,
    ClinicalNoteResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

# LLM singleton helper
_llm_provider: Optional[LLMProviderInterface] = None


def get_llm_provider() -> LLMProviderInterface:
    global _llm_provider
    if _llm_provider is None:
        _llm_provider = FallbackLLMProvider()
    return _llm_provider


def require_doctor_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency enforcing that the authenticated user has verified doctor privileges."""
    clinical_notes_service._get_doctor_record(current_user)
    return current_user


# ============================================================
# 1. AUDIO TRANSCRIPTION ENDPOINT
# ============================================================

@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    summary="Transcribe Doctor-Patient Audio Consultation"
)
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(require_doctor_user),
    stt_service: AudioTranscriptionService = Depends(get_transcription_service)
) -> TranscriptionResponse:
    """
    Transcribes audio recorded via browser microphone or uploaded audio file.
    Doctor-only access. Temporary raw audio is destroyed immediately after processing.
    """
    logger.info(f"Doctor '{current_user.get('id')}' submitted audio for transcription ({file.filename})")
    result = await stt_service.transcribe_audio_file(file)
    return TranscriptionResponse(**result)


# ============================================================
# 2. SOAP NOTE GENERATION ENDPOINT
# ============================================================

@router.post(
    "/generate-soap",
    response_model=SoapGenerateResponse,
    summary="Generate Structured SOAP Note Draft from Transcript"
)
async def generate_soap_note(
    request: SoapGenerateRequest,
    current_user: Dict[str, Any] = Depends(require_doctor_user),
    llm: LLMProviderInterface = Depends(get_llm_provider)
) -> SoapGenerateResponse:
    """
    Uses CareFlow AI's clinical LLM provider (Gemini) to generate a structured 4-section
    SOAP draft (Subjective, Objective, Assessment, Plan) from the transcript.
    Strictly forbids hallucinations and labels output as an AI draft requiring review.
    """
    if not request.transcript or not request.transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Consultation transcript cannot be empty."
        )

    try:
        generator = SoapNoteGenerator(llm_provider=llm)
        response = await generator.generate_soap_note(
            transcript=request.transcript,
            patient_context=request.patient_context
        )
        return response

    except LLMAuthenticationError as e:
        logger.error(f"SOAP generation auth error: {e.detail}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.detail)
    except LLMRateLimitError as e:
        logger.warning(f"SOAP generation rate limit: {e.detail}")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=e.detail)
    except LLMTimeoutError as e:
        logger.error(f"SOAP generation timeout: {e.detail}")
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=e.detail)
    except LLMServiceUnavailableError as e:
        logger.warning(f"SOAP generation provider unavailable: {e.detail}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=e.detail)
    except LLMProviderError as e:
        logger.error(f"SOAP generation provider failure: {e.detail}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=e.detail)
    except Exception as e:
        logger.error(f"Unexpected SOAP generation error: {type(e).__name__} - {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the SOAP note draft."
        )


# ============================================================
# 3. CLINICAL NOTES PERSISTENCE & APPROVAL ENDPOINTS
# ============================================================

@router.post(
    "",
    response_model=ClinicalNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Save Clinical Note Draft"
)
async def create_clinical_note(
    payload: ClinicalNoteCreate,
    current_user: Dict[str, Any] = Depends(require_doctor_user)
) -> ClinicalNoteResponse:
    """Save a new clinical note draft authored by the doctor."""
    return clinical_notes_service.create_clinical_note(payload, current_user)


@router.get(
    "",
    response_model=List[ClinicalNoteResponse],
    summary="List Clinical Notes"
)
async def list_clinical_notes(
    patient_id: Optional[str] = Query(None, description="Filter by patient UUID"),
    appointment_id: Optional[str] = Query(None, description="Filter by appointment UUID"),
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> List[ClinicalNoteResponse]:
    """
    List clinical notes:
    - Doctors view notes they authored.
    - Patients view approved notes assigned to their profile.
    """
    return clinical_notes_service.list_clinical_notes(
        current_user=current_user,
        patient_id=patient_id,
        appointment_id=appointment_id
    )


@router.get(
    "/{note_id}",
    response_model=ClinicalNoteResponse,
    summary="Get Specific Clinical Note"
)
async def get_clinical_note(
    note_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> ClinicalNoteResponse:
    """Retrieve details of a single clinical note enforcing authorization."""
    return clinical_notes_service.get_clinical_note_by_id(note_id, current_user)


@router.put(
    "/{note_id}",
    response_model=ClinicalNoteResponse,
    summary="Update Clinical Note Draft"
)
async def update_clinical_note(
    note_id: str,
    payload: ClinicalNoteUpdate,
    current_user: Dict[str, Any] = Depends(require_doctor_user)
) -> ClinicalNoteResponse:
    """Update sections or status of an existing clinical note draft."""
    return clinical_notes_service.update_clinical_note(note_id, payload, current_user)


@router.post(
    "/{note_id}/approve",
    response_model=ClinicalNoteResponse,
    summary="Approve and Finalize Clinical Note"
)
async def approve_clinical_note(
    note_id: str,
    current_user: Dict[str, Any] = Depends(require_doctor_user)
) -> ClinicalNoteResponse:
    """
    Formally mark a clinical note as reviewed and approved by the attending physician.
    Enforces that only the authoring doctor can approve.
    """
    return clinical_notes_service.approve_clinical_note(note_id, current_user)


# ============================================================
# 4. PRESCRIPTION GENERATION & PDF EXPORT ENDPOINTS
# ============================================================

@router.get(
    "/{note_id}/prescription-pdf",
    summary="Download Print-Ready Doctor Prescription PDF",
    response_class=Response
)
async def download_prescription_pdf(
    note_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Generates and returns an authentic, single-page A4 Doctor Prescription PDF.
    - Verified attending doctor can generate for their authored clinical encounters.
    - Assigned patient can download approved prescriptions.
    - Uses saved SOAP data without LLM re-invocation.
    """
    result = prescription_pdf_service.generate_for_clinical_note(note_id, current_user)
    if result.get("status_code") != 200:
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result.get("error", "Failed to generate prescription PDF.")
        )

    pdf_bytes = result["pdf_bytes"]
    filename = result["filename"]

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )


@router.get(
    "/{note_id}/prescription-data",
    summary="Get Structured Prescription Details for Note",
    response_model=Dict[str, Any]
)
async def get_prescription_data(
    note_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Returns verified, structured prescription items (medications, vitals,
    diagnosis, advice, and any incomplete field flags) extracted from the SOAP record.
    """
    result = prescription_pdf_service.generate_for_clinical_note(note_id, current_user)
    if result.get("status_code") != 200:
        raise HTTPException(
            status_code=result.get("status_code", 400),
            detail=result.get("error", "Failed to retrieve prescription data.")
        )

    return result["prescription_data"]

