from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime


class TranscriptionResponse(BaseModel):
    transcript: str = Field(..., description="Transcribed text from audio")
    language: Optional[str] = Field("en", description="Detected language code")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")


class SoapGenerateRequest(BaseModel):
    transcript: str = Field(..., min_length=1, description="Medical dialogue or consultation transcript")
    patient_context: Optional[str] = Field(None, description="Optional patient name, age, gender, reason for visit")


class SoapSections(BaseModel):
    subjective: str = Field(..., description="Subjective symptoms, history, and patient complaints")
    objective: str = Field(..., description="Objective physical examination findings and vital signs")
    assessment: str = Field(..., description="Clinician diagnosis or clinical assessment")
    plan: str = Field(..., description="Treatment, medication, testing, and follow-up plan")


class AIModelAttribution(BaseModel):
    provider: str = Field("Google Gemini", description="AI provider name")
    model: str = Field(..., description="Actual model that generated the response")
    fallback_used: bool = Field(False, description="Whether fallback model was used")
    attempted_models: List[str] = Field(default_factory=list, description="Sequence of attempted models")


class SoapGenerateResponse(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
    disclaimer: str = (
        "AI-Generated Clinical Draft: This note requires physician review, "
        "verification, and explicit clinical approval before being finalized."
    )
    model_attribution: Optional[AIModelAttribution] = None


class ClinicalNoteCreate(BaseModel):
    patient_id: str = Field(..., description="UUID of the patient")
    appointment_id: Optional[str] = Field(None, description="Optional UUID of the associated appointment")
    transcript: str = Field(..., min_length=1, description="Raw or corrected consultation transcript")
    subjective: str = Field(default="Not documented")
    objective: str = Field(default="Not documented")
    assessment: str = Field(default="Not documented")
    plan: str = Field(default="Not documented")
    status: str = Field(default="draft", description="Status: draft, reviewed, or approved")


class ClinicalNoteUpdate(BaseModel):
    transcript: Optional[str] = None
    subjective: Optional[str] = None
    objective: Optional[str] = None
    assessment: Optional[str] = None
    plan: Optional[str] = None
    status: Optional[str] = None


class ClinicalNoteResponse(BaseModel):
    id: str
    doctor_id: str
    patient_id: str
    appointment_id: Optional[str] = None
    transcript: str
    subjective: str
    objective: str
    assessment: str
    plan: str
    status: str
    reviewed_at: Optional[str] = None
    created_at: str
    updated_at: str
    patient_name: Optional[str] = "Patient"
    doctor_name: Optional[str] = "Doctor"
