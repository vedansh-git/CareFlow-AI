import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
import httpx

from app.core.config import settings
from app.services.data_store import db_store
from app.schemas.clinical_notes import (
    ClinicalNoteCreate,
    ClinicalNoteUpdate,
    ClinicalNoteResponse,
)

logger = logging.getLogger(__name__)


class ClinicalNotesService:
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL.rstrip('/') if settings.SUPABASE_URL else ""
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.anon_key = settings.SUPABASE_ANON_KEY or settings.SUPABASE_SERVICE_ROLE_KEY

    def _get_doctor_record(self, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves verified doctor record or raises 403."""
        profile_id = current_user.get("id")
        app_role = current_user.get("app_role", "patient")

        # 1. Check local db_store for doctor record
        doc = db_store.get_doctor_by_profile_id(profile_id)
        if doc:
            if not doc.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access restricted: Your doctor account is currently marked inactive or unverified."
                )
            return doc

        # 2. Check Supabase profiles & doctors table if configured
        if self.supabase_url:
            try:
                headers = {
                    "apikey": self.service_key or self.anon_key,
                    "Authorization": f"Bearer {self.service_key or self.anon_key}",
                }
                with httpx.Client(timeout=5.0) as client:
                    # Check profile role
                    p_res = client.get(
                        f"{self.supabase_url}/rest/v1/profiles?id=eq.{profile_id}&select=role,full_name",
                        headers=headers
                    )
                    if p_res.status_code == 200:
                        p_data = p_res.json()
                        if p_data and len(p_data) > 0 and p_data[0].get("role") == "doctor":
                            full_name = p_data[0].get("full_name") or current_user.get("full_name", "Doctor")
                            
                            # Check active status in doctors table
                            d_res = client.get(
                                f"{self.supabase_url}/rest/v1/doctors?profile_id=eq.{profile_id}&select=id,profile_id,specialty,qualification,bio,is_active",
                                headers=headers
                            )
                            if d_res.status_code == 200:
                                d_data = d_res.json()
                                if d_data and len(d_data) > 0:
                                    doc_rec = d_data[0]
                                    if not doc_rec.get("is_active", True):
                                        raise HTTPException(
                                            status_code=status.HTTP_403_FORBIDDEN,
                                            detail="Access restricted: Your doctor account is currently marked inactive."
                                        )
                                    # Sync/Cache into db_store
                                    db_store.doctors[doc_rec["id"]] = doc_rec
                                    db_store.profiles[profile_id] = {
                                        "id": profile_id,
                                        "full_name": full_name,
                                        "role": "doctor",
                                        "email": current_user.get("email"),
                                    }
                                    return doc_rec
                            
                            # If profile is doctor, create and sync active doctor record in db_store
                            new_doc = db_store.create_or_update_doctor(
                                profile_id=profile_id,
                                specialty="General Medicine",
                                qualification="MD"
                            )
                            db_store.profiles[profile_id] = {
                                "id": profile_id,
                                "full_name": full_name,
                                "role": "doctor",
                                "email": current_user.get("email"),
                            }
                            return new_doc
            except HTTPException:
                raise
            except Exception as err:
                logger.warning(f"Error checking Supabase doctor profile: {err}")

        # 3. If current_user has app_role == 'doctor' (e.g. from token / auth override)
        if app_role == "doctor":
            doc = db_store.get_doctor_by_profile_id(profile_id)
            if doc and not doc.get("is_active", True):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access restricted: Your doctor account is currently marked inactive or unverified."
                )
            if not doc:
                doc = db_store.create_or_update_doctor(profile_id=profile_id)
            return doc

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: This clinical documentation action requires a verified Doctor account."
        )

    def _get_patient_record(self, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves patient record for patient users."""
        profile_id = current_user.get("id")
        return db_store.get_or_create_patient(
            profile_id=profile_id,
            full_name=current_user.get("full_name", "Patient"),
            email=current_user.get("email")
        )

    def _resolve_appointment(self, appointment_id: str, doc_id: str) -> Optional[Dict[str, Any]]:
        if not appointment_id:
            return None

        # 1. Check in-memory store
        appt = db_store.get_appointment_by_id(appointment_id)
        if appt:
            return appt

        # 2. Check Supabase appointments table if configured
        if self.supabase_url:
            try:
                headers = {
                    "apikey": self.service_key or self.anon_key,
                    "Authorization": f"Bearer {self.service_key or self.anon_key}",
                }
                with httpx.Client(timeout=5.0) as client:
                    a_res = client.get(
                        f"{self.supabase_url}/rest/v1/appointments?id=eq.{appointment_id}",
                        headers=headers
                    )
                    if a_res.status_code == 200:
                        a_data = a_res.json()
                        if a_data and len(a_data) > 0:
                            raw_appt = a_data[0]
                            # Cache in db_store
                            db_store.appointments[raw_appt["id"]] = {
                                "id": raw_appt["id"],
                                "patient_id": raw_appt.get("patient_id"),
                                "doctor_id": raw_appt.get("doctor_id", doc_id),
                                "appointment_date": str(raw_appt.get("appointment_date")),
                                "start_time": str(raw_appt.get("start_time")),
                                "end_time": str(raw_appt.get("end_time")),
                                "reason": raw_appt.get("reason"),
                                "status": raw_appt.get("status", "scheduled"),
                                "notes": raw_appt.get("notes"),
                                "created_at": raw_appt.get("created_at"),
                                "updated_at": raw_appt.get("updated_at"),
                            }
                            return db_store.get_appointment_by_id(appointment_id)
            except Exception as err:
                logger.warning(f"Error querying Supabase appointment '{appointment_id}': {err}")

        return None

    def create_clinical_note(
        self,
        payload: ClinicalNoteCreate,
        current_user: Dict[str, Any]
    ) -> ClinicalNoteResponse:
        doc = self._get_doctor_record(current_user)

        # Validate transcript
        if not payload.transcript or not payload.transcript.strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Consultation transcript cannot be empty."
            )

        patient_id = payload.patient_id

        # If appointment_id provided, verify or resolve appointment
        if payload.appointment_id:
            appt = self._resolve_appointment(payload.appointment_id, doc["id"])
            if appt:
                if appt.get("doctor_id") and appt["doctor_id"] != doc["id"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access restricted: Doctors can only create clinical notes for their own assigned appointments."
                    )
                if appt.get("patient_id"):
                    patient_id = appt["patient_id"]
            else:
                logger.info(f"Appointment '{payload.appointment_id}' not found in database; saving clinical encounter with reference ID.")

        # Ensure valid patient ID fallback if placeholder was sent
        if not patient_id or patient_id in ("00000000-0000-0000-0000-000000000000", "patient-1", ""):
            if not db_store.patients.get(patient_id):
                fallback_pat = db_store.get_or_create_patient(
                    profile_id="patient-prof-general",
                    full_name="Consultation Patient",
                    email="patient@careflow.ai"
                )
                patient_id = fallback_pat["id"]

        note_data = db_store.create_clinical_note(
            doctor_id=doc["id"],
            patient_id=patient_id,
            appointment_id=payload.appointment_id,
            transcript=payload.transcript.strip(),
            subjective=payload.subjective or "Not documented",
            objective=payload.objective or "Not documented",
            assessment=payload.assessment or "Not documented",
            plan=payload.plan or "Not documented",
            status=payload.status or "draft"
        )

        return ClinicalNoteResponse(**note_data)


    def get_clinical_note_by_id(
        self,
        note_id: str,
        current_user: Dict[str, Any]
    ) -> ClinicalNoteResponse:
        note = db_store.get_clinical_note_by_id(note_id)
        if not note:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clinical note '{note_id}' not found."
            )

        app_role = current_user.get("app_role", "patient")
        profile_id = current_user.get("id")

        if app_role == "doctor":
            doc = self._get_doctor_record(current_user)
            if note["doctor_id"] != doc["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You do not have permission to view this clinical note."
                )
        else:
            patient = self._get_patient_record(current_user)
            if note["patient_id"] != patient["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You cannot access another patient's clinical note."
                )
            if note["status"] not in ("reviewed", "approved"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Clinical note draft is still under physician review."
                )

        return ClinicalNoteResponse(**note)

    def list_clinical_notes(
        self,
        current_user: Dict[str, Any],
        patient_id: Optional[str] = None,
        appointment_id: Optional[str] = None
    ) -> List[ClinicalNoteResponse]:
        app_role = current_user.get("app_role", "patient")

        if app_role == "doctor":
            doc = self._get_doctor_record(current_user)
            notes = db_store.list_clinical_notes_for_doctor(
                doctor_id=doc["id"],
                patient_id=patient_id,
                appointment_id=appointment_id
            )
            return [ClinicalNoteResponse(**n) for n in notes]
        else:
            patient = self._get_patient_record(current_user)
            notes = db_store.list_clinical_notes_for_patient(patient["id"])
            return [ClinicalNoteResponse(**n) for n in notes]

    def update_clinical_note(
        self,
        note_id: str,
        payload: ClinicalNoteUpdate,
        current_user: Dict[str, Any]
    ) -> ClinicalNoteResponse:
        doc = self._get_doctor_record(current_user)

        existing = db_store.get_clinical_note_by_id(note_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clinical note '{note_id}' not found."
            )

        if existing["doctor_id"] != doc["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You cannot modify a note authored by another physician."
            )

        update_dict = payload.model_dump(exclude_unset=True)
        updated = db_store.update_clinical_note(note_id, update_dict)
        return ClinicalNoteResponse(**updated)

    def approve_clinical_note(
        self,
        note_id: str,
        current_user: Dict[str, Any]
    ) -> ClinicalNoteResponse:
        doc = self._get_doctor_record(current_user)

        existing = db_store.get_clinical_note_by_id(note_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Clinical note '{note_id}' not found."
            )

        if existing["doctor_id"] != doc["id"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized: You cannot approve a clinical note authored by another physician."
            )

        updated = db_store.update_clinical_note(note_id, {"status": "approved"})
        return ClinicalNoteResponse(**updated)


clinical_notes_service = ClinicalNotesService()
