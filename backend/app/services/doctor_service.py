import httpx
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.data_store import db_store, parse_time_str
from app.schemas.doctor import (
    DoctorResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityCreate,
    DoctorAvailabilityUpdate,
)


class DoctorService:
    @staticmethod
    def get_all_active_doctors() -> List[DoctorResponse]:
        doctors_data = db_store.get_all_active_doctors()
        return [DoctorResponse(**doc) for doc in doctors_data]

    @staticmethod
    def get_doctor_by_id(doctor_id: str) -> DoctorResponse:
        doc = db_store.get_doctor_by_id(doctor_id)
        if not doc or not doc.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with ID '{doctor_id}' not found or inactive",
            )
        return DoctorResponse(**doc)

    @staticmethod
    def get_doctor_by_profile_id(profile_id: str) -> DoctorResponse:
        doc = db_store.get_doctor_by_profile_id(profile_id)
        if doc:
            return DoctorResponse(**doc)

        # Check Supabase if configured
        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=5.0) as client:
                    # Check profile role
                    p_res = client.get(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/profiles?id=eq.{profile_id}&select=role,full_name,email",
                        headers=headers
                    )
                    if p_res.status_code == 200:
                        p_data = p_res.json()
                        if p_data and len(p_data) > 0 and p_data[0].get("role") == "doctor":
                            full_name = p_data[0].get("full_name") or "Doctor"
                            email = p_data[0].get("email")

                            # Check doctor profile in doctors table
                            d_res = client.get(
                                f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/doctors?profile_id=eq.{profile_id}&select=id,profile_id,specialty,qualification,bio,is_active",
                                headers=headers
                            )
                            if d_res.status_code == 200:
                                d_data = d_res.json()
                                if d_data and len(d_data) > 0:
                                    doc_rec = d_data[0]
                                    db_store.doctors[doc_rec["id"]] = doc_rec
                                    db_store.profiles[profile_id] = {
                                        "id": profile_id,
                                        "full_name": full_name,
                                        "role": "doctor",
                                        "email": email,
                                    }
                                    return DoctorResponse(
                                        id=doc_rec["id"],
                                        profile_id=doc_rec["profile_id"],
                                        full_name=full_name,
                                        email=email,
                                        specialty=doc_rec.get("specialty"),
                                        qualification=doc_rec.get("qualification"),
                                        bio=doc_rec.get("bio"),
                                        is_active=doc_rec.get("is_active", True)
                                    )

                            # Fallback: create & cache doctor profile
                            new_doc = db_store.create_or_update_doctor(profile_id=profile_id)
                            db_store.profiles[profile_id] = {
                                "id": profile_id,
                                "full_name": full_name,
                                "role": "doctor",
                                "email": email,
                            }
                            return DoctorResponse(**new_doc)
            except Exception:
                pass

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor profile not found for the authenticated user",
        )

    @staticmethod
    def get_doctor_availability(doctor_id: str) -> List[DoctorAvailabilityResponse]:
        # Validate doctor exists
        DoctorService.get_doctor_by_id(doctor_id)
        slots = db_store.get_doctor_availability(doctor_id, only_active=True)
        return [DoctorAvailabilityResponse(**s) for s in slots]

    @staticmethod
    def get_doctor_me_availability(profile_id: str) -> List[DoctorAvailabilityResponse]:
        doc = DoctorService.get_doctor_by_profile_id(profile_id)
        slots = db_store.get_doctor_availability(doc.id, only_active=False)
        return [DoctorAvailabilityResponse(**s) for s in slots]

    @staticmethod
    def add_doctor_availability(
        profile_id: str,
        payload: DoctorAvailabilityCreate
    ) -> DoctorAvailabilityResponse:
        doc = DoctorService.get_doctor_by_profile_id(profile_id)
        try:
            start_t = parse_time_str(payload.start_time)
            end_t = parse_time_str(payload.end_time)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

        if start_t >= end_t:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be earlier than end_time",
            )

        slot = db_store.add_doctor_availability(
            doctor_id=doc.id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_active=payload.is_active,
        )
        return DoctorAvailabilityResponse(**slot)

    @staticmethod
    def update_doctor_availability(
        profile_id: str,
        availability_id: str,
        payload: DoctorAvailabilityUpdate
    ) -> DoctorAvailabilityResponse:
        doc = DoctorService.get_doctor_by_profile_id(profile_id)
        existing = db_store.doctor_availability.get(availability_id)
        if not existing or existing.get("doctor_id") != doc.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found or unauthorized",
            )

        if payload.start_time or payload.end_time:
            st_str = payload.start_time or existing["start_time"]
            et_str = payload.end_time or existing["end_time"]
            start_t = parse_time_str(st_str)
            end_t = parse_time_str(et_str)
            if start_t >= end_t:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="start_time must be earlier than end_time",
                )

        updated = db_store.update_doctor_availability(
            slot_id=availability_id,
            day_of_week=payload.day_of_week,
            start_time=payload.start_time,
            end_time=payload.end_time,
            is_active=payload.is_active,
        )
        return DoctorAvailabilityResponse(**updated)

    @staticmethod
    def delete_doctor_availability(profile_id: str, availability_id: str) -> Dict[str, Any]:
        doc = DoctorService.get_doctor_by_profile_id(profile_id)
        existing = db_store.doctor_availability.get(availability_id)
        if not existing or existing.get("doctor_id") != doc.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Availability slot not found or unauthorized",
            )
        db_store.delete_doctor_availability(availability_id)
        return {"success": True, "message": "Availability slot deleted"}


doctor_service = DoctorService()
