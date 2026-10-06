import logging
import httpx
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from app.core.config import settings
from app.services.data_store import db_store, parse_time_str, DAY_NAMES, format_time_str
from app.schemas.doctor import (
    DoctorResponse,
    DoctorAvailabilityResponse,
    DoctorAvailabilityCreate,
    DoctorAvailabilityUpdate,
)

logger = logging.getLogger(__name__)


class DoctorService:
    @staticmethod
    def _format_supabase_doctor(doc_row: Dict[str, Any]) -> Dict[str, Any]:
        """Maps a Supabase doctor row (with joined profiles) into a standard doctor dictionary."""
        prof = doc_row.get("profiles") or {}
        if isinstance(prof, list) and len(prof) > 0:
            prof = prof[0]
        elif not isinstance(prof, dict):
            prof = {}

        doc_id = str(doc_row["id"])
        profile_id = str(doc_row.get("profile_id") or prof.get("id") or "")
        full_name = prof.get("full_name") or "Doctor"
        email = prof.get("email")
        phone = prof.get("phone") or "+1-555-0100"

        # Check if we have cached metadata or reviews in db_store for this doctor
        existing_store_doc = db_store.doctors.get(doc_id) or {}

        return {
            "id": doc_id,
            "profile_id": profile_id,
            "full_name": full_name,
            "email": email,
            "specialty": doc_row.get("specialty") or existing_store_doc.get("specialty") or "General Medicine",
            "qualification": doc_row.get("qualification") or existing_store_doc.get("qualification") or "MD",
            "bio": doc_row.get("bio") or existing_store_doc.get("bio") or "",
            "clinic_address": doc_row.get("clinic_address") or existing_store_doc.get("clinic_address") or "CareFlow Medical Centre, Main Campus",
            "contact_phone": doc_row.get("contact_phone") or phone,
            "experience_years": doc_row.get("experience_years") or existing_store_doc.get("experience_years") or 10,
            "consultation_fee": float(doc_row.get("consultation_fee") or existing_store_doc.get("consultation_fee") or 100.0),
            "rating": float(doc_row.get("rating") or existing_store_doc.get("rating") or 4.8),
            "reviews_count": int(doc_row.get("reviews_count") or existing_store_doc.get("reviews_count") or 15),
            "demo_reviews": doc_row.get("demo_reviews") or existing_store_doc.get("demo_reviews") or [],
            "is_active": doc_row.get("is_active", True),
        }

    @staticmethod
    def _sync_doctor_to_store(doc_dict: Dict[str, Any]):
        """Synchronizes live doctor and profile records into in-memory store for downstream helpers."""
        try:
            doc_id = doc_dict["id"]
            profile_id = doc_dict["profile_id"]
            db_store.doctors[doc_id] = {
                "id": doc_id,
                "profile_id": profile_id,
                "specialty": doc_dict.get("specialty"),
                "qualification": doc_dict.get("qualification"),
                "bio": doc_dict.get("bio"),
                "clinic_address": doc_dict.get("clinic_address"),
                "contact_phone": doc_dict.get("contact_phone"),
                "experience_years": doc_dict.get("experience_years"),
                "consultation_fee": doc_dict.get("consultation_fee"),
                "rating": doc_dict.get("rating"),
                "reviews_count": doc_dict.get("reviews_count"),
                "demo_reviews": doc_dict.get("demo_reviews"),
                "is_active": doc_dict.get("is_active", True),
            }
            db_store.profiles[profile_id] = {
                "id": profile_id,
                "full_name": doc_dict.get("full_name"),
                "role": "doctor",
                "email": doc_dict.get("email"),
                "phone": doc_dict.get("contact_phone"),
            }
        except Exception as e:
            logger.warning(f"Failed to sync doctor to in-memory store: {e}")

    @staticmethod
    def get_all_active_doctors() -> List[DoctorResponse]:
        """
        Retrieves all active doctors:
        1. Live Supabase query (priority source of truth)
        2. Merges and syncs with in-memory store
        3. Falls back to in-memory seed store if Supabase is unavailable
        """
        supabase_doctors: List[Dict[str, Any]] = []

        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=4.0) as client:
                    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/doctors?select=id,profile_id,specialty,qualification,bio,is_active,profiles(id,full_name,role,phone)&is_active=eq.true"
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list):
                            for item in data:
                                if item.get("is_active", True):
                                    formatted = DoctorService._format_supabase_doctor(item)
                                    DoctorService._sync_doctor_to_store(formatted)
                                    supabase_doctors.append(formatted)
            except Exception as e:
                logger.warning(f"Live Supabase get_all_active_doctors failed, falling back to local store: {e}")

        # If Supabase returned live doctors, merge with local store (Supabase live data takes priority)
        if supabase_doctors:
            seen_ids = set(d["id"] for d in supabase_doctors)
            seen_profiles = set(d["profile_id"] for d in supabase_doctors)
            merged = list(supabase_doctors)

            # Include any local seed doctors that are not yet in Supabase
            for local_doc in db_store.get_all_active_doctors():
                if local_doc["id"] not in seen_ids and local_doc.get("profile_id") not in seen_profiles:
                    merged.append(local_doc)

            return [DoctorResponse(**d) for d in merged]

        # Supabase unavailable / returned empty: fallback to db_store
        doctors_data = db_store.get_all_active_doctors()
        return [DoctorResponse(**doc) for doc in doctors_data]

    @staticmethod
    def get_doctor_by_id(doctor_id: str) -> DoctorResponse:
        """
        Retrieves specific doctor details:
        1. Queries Supabase by doctor_id
        2. Falls back to in-memory store
        """
        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=4.0) as client:
                    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/doctors?id=eq.{doctor_id}&select=id,profile_id,specialty,qualification,bio,is_active,profiles(id,full_name,role,phone)&is_active=eq.true"
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            formatted = DoctorService._format_supabase_doctor(data[0])
                            DoctorService._sync_doctor_to_store(formatted)
                            return DoctorResponse(**formatted)
            except Exception as e:
                logger.warning(f"Live Supabase get_doctor_by_id failed, falling back: {e}")

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
                with httpx.Client(timeout=4.0) as client:
                    # Check profile role
                    p_res = client.get(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/profiles?id=eq.{profile_id}&select=role,full_name,email,phone",
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
                                    doc_rec["profiles"] = p_data[0]
                                    formatted = DoctorService._format_supabase_doctor(doc_rec)
                                    DoctorService._sync_doctor_to_store(formatted)
                                    return DoctorResponse(**formatted)

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
        """
        Retrieves active weekly availability for a doctor:
        1. Queries Supabase doctor_availability table
        2. Falls back to db_store
        3. If no custom slots exist, provides standard hours (Mon-Fri 09:00-17:00, Sat 09:00-13:00)
        """
        # Validate doctor exists
        DoctorService.get_doctor_by_id(doctor_id)

        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=4.0) as client:
                    url = f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/doctor_availability?doctor_id=eq.{doctor_id}&is_active=eq.true&order=day_of_week.asc,start_time.asc"
                    res = client.get(url, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            supa_slots = []
                            for s in data:
                                day_num = int(s["day_of_week"])
                                st = format_time_str(s["start_time"])
                                et = format_time_str(s["end_time"])
                                slot_dict = {
                                    "id": str(s["id"]),
                                    "doctor_id": str(s["doctor_id"]),
                                    "day_of_week": day_num,
                                    "day_name": DAY_NAMES.get(day_num, "Unknown"),
                                    "start_time": st,
                                    "end_time": et,
                                    "is_active": s.get("is_active", True),
                                }
                                db_store.doctor_availability[str(s["id"])] = slot_dict
                                supa_slots.append(DoctorAvailabilityResponse(**slot_dict))
                            return supa_slots
            except Exception as e:
                logger.warning(f"Live Supabase get_doctor_availability failed, falling back: {e}")

        # Fallback to local store
        slots = db_store.get_doctor_availability(doctor_id, only_active=True)
        if slots:
            return [DoctorAvailabilityResponse(**s) for s in slots]

        # Standard schedule fallback for newly registered doctors
        standard_slots = []
        for day in range(1, 6):  # Mon - Fri
            s_dict = {
                "id": f"std-slot-{doctor_id}-{day}",
                "doctor_id": doctor_id,
                "day_of_week": day,
                "day_name": DAY_NAMES.get(day, "Unknown"),
                "start_time": "09:00",
                "end_time": "17:00",
                "is_active": True,
            }
            db_store.doctor_availability[s_dict["id"]] = s_dict
            standard_slots.append(DoctorAvailabilityResponse(**s_dict))

        # Saturday
        sat_dict = {
            "id": f"std-slot-{doctor_id}-6",
            "doctor_id": doctor_id,
            "day_of_week": 6,
            "day_name": DAY_NAMES.get(6, "Saturday"),
            "start_time": "09:00",
            "end_time": "13:00",
            "is_active": True,
        }
        db_store.doctor_availability[sat_dict["id"]] = sat_dict
        standard_slots.append(DoctorAvailabilityResponse(**sat_dict))

        return standard_slots

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

