from datetime import datetime, date
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
import httpx
from app.core.config import settings
from app.services.data_store import (
    db_store,
    parse_time_str,
    get_db_day_of_week,
    DAY_NAMES,
)
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentResponse,
    AppointmentUpdate,
    AppointmentStatusEnum,
)


class AppointmentService:
    @staticmethod
    def get_user_appointments(current_user: Dict[str, Any]) -> List[AppointmentResponse]:
        profile_id = current_user.get("id")
        app_role = current_user.get("app_role", "patient")

        if app_role == "doctor":
            # 1. Try Supabase REST query if configured
            if settings.SUPABASE_URL:
                try:
                    profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                    headers = {
                        "apikey": profile_key,
                        "Authorization": f"Bearer {profile_key}",
                    }
                    with httpx.Client(timeout=5.0) as client:
                        # Find doctor id for this profile_id
                        d_res = client.get(
                            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/doctors?profile_id=eq.{profile_id}&select=id",
                            headers=headers
                        )
                        if d_res.status_code == 200:
                            d_json = d_res.json()
                            if d_json and len(d_json) > 0:
                                doc_id = d_json[0]["id"]
                                a_res = client.get(
                                    f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments?doctor_id=eq.{doc_id}&select=*,doctors(id,specialty,profiles(full_name)),patients(id,profiles(full_name))&order=appointment_date.asc,start_time.asc",
                                    headers=headers
                                )
                                if a_res.status_code == 200:
                                    supa_appts = []
                                    for a in a_res.json():
                                        doc_data = a.get("doctors") or {}
                                        doc_prof = doc_data.get("profiles") or {}
                                        pat_data = a.get("patients") or {}
                                        pat_prof = pat_data.get("profiles") or {}
                                        supa_appts.append(AppointmentResponse(
                                            id=a["id"],
                                            patient_id=a["patient_id"],
                                            doctor_id=a["doctor_id"],
                                            appointment_date=str(a["appointment_date"]),
                                            start_time=str(a["start_time"]),
                                            end_time=str(a["end_time"]),
                                            reason=a.get("reason"),
                                            status=a.get("status", "scheduled"),
                                            notes=a.get("notes"),
                                            created_at=a.get("created_at"),
                                            updated_at=a.get("updated_at"),
                                            doctor_name=doc_prof.get("full_name") or "Doctor",
                                            doctor_specialty=doc_data.get("specialty") or "General Medicine",
                                            patient_name=pat_prof.get("full_name") or "Patient",
                                        ))
                                    return supa_appts
                except Exception as e:
                    print(f"Supabase doctor appointments query error: {e}")

            doc = db_store.get_doctor_by_profile_id(profile_id)
            if not doc:
                return []
            appts = db_store.get_appointments_for_doctor(doc["id"])
            return [AppointmentResponse(**a) for a in appts]
        else:
            # 1. Try Supabase REST query if configured
            if settings.SUPABASE_URL:
                try:
                    profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                    headers = {
                        "apikey": profile_key,
                        "Authorization": f"Bearer {profile_key}",
                    }
                    with httpx.Client(timeout=5.0) as client:
                        # Find patient id for this profile_id
                        p_res = client.get(
                            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/patients?profile_id=eq.{profile_id}&select=id",
                            headers=headers
                        )
                        if p_res.status_code == 200:
                            p_json = p_res.json()
                            if p_json and len(p_json) > 0:
                                patient_id = p_json[0]["id"]
                                a_res = client.get(
                                    f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments?patient_id=eq.{patient_id}&select=*,doctors(id,specialty,profiles(full_name)),patients(id,profiles(full_name))&order=appointment_date.asc,start_time.asc",
                                    headers=headers
                                )
                                if a_res.status_code == 200:
                                    supa_appts = []
                                    for a in a_res.json():
                                        doc_data = a.get("doctors") or {}
                                        doc_prof = doc_data.get("profiles") or {}
                                        pat_data = a.get("patients") or {}
                                        pat_prof = pat_data.get("profiles") or {}
                                        supa_appts.append(AppointmentResponse(
                                            id=a["id"],
                                            patient_id=a["patient_id"],
                                            doctor_id=a["doctor_id"],
                                            appointment_date=str(a["appointment_date"]),
                                            start_time=str(a["start_time"]),
                                            end_time=str(a["end_time"]),
                                            reason=a.get("reason"),
                                            status=a.get("status", "scheduled"),
                                            notes=a.get("notes"),
                                            created_at=a.get("created_at"),
                                            updated_at=a.get("updated_at"),
                                            doctor_name=doc_prof.get("full_name") or "Doctor",
                                            doctor_specialty=doc_data.get("specialty") or "General Medicine",
                                            patient_name=pat_prof.get("full_name") or "Patient",
                                        ))
                                    return supa_appts
                except Exception as e:
                    print(f"Supabase patient appointments query error: {e}")

            patient = db_store.get_or_create_patient(
                profile_id=profile_id,
                full_name=current_user.get("full_name", "Patient"),
                email=current_user.get("email"),
            )
            appts = db_store.get_appointments_for_patient(patient["id"])
            return [AppointmentResponse(**a) for a in appts]

    @staticmethod
    def get_appointment_by_id(appointment_id: str, current_user: Dict[str, Any]) -> AppointmentResponse:
        profile_id = current_user.get("id")
        app_role = current_user.get("app_role", "patient")

        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=5.0) as client:
                    a_res = client.get(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments?id=eq.{appointment_id}&select=*,doctors(id,profile_id,specialty,profiles(full_name)),patients(id,profile_id,profiles(full_name))",
                        headers=headers
                    )
                    if a_res.status_code == 200 and a_res.json():
                        a = a_res.json()[0]
                        doc_data = a.get("doctors") or {}
                        doc_prof = doc_data.get("profiles") or {}
                        pat_data = a.get("patients") or {}
                        pat_prof = pat_data.get("profiles") or {}
                        doc_profile_id = doc_data.get("profile_id")
                        pat_profile_id = pat_data.get("profile_id")

                        if app_role == "doctor" and doc_profile_id != profile_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Unauthorized: You do not have access to this appointment",
                            )
                        elif app_role != "doctor" and pat_profile_id != profile_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="Unauthorized: You do not have access to another patient's appointment",
                            )

                        return AppointmentResponse(
                            id=a["id"],
                            patient_id=a["patient_id"],
                            doctor_id=a["doctor_id"],
                            appointment_date=str(a["appointment_date"]),
                            start_time=str(a["start_time"]),
                            end_time=str(a["end_time"]),
                            reason=a.get("reason"),
                            status=a.get("status", "scheduled"),
                            notes=a.get("notes"),
                            created_at=a.get("created_at"),
                            updated_at=a.get("updated_at"),
                            doctor_name=doc_prof.get("full_name") or "Doctor",
                            doctor_specialty=doc_data.get("specialty") or "General Medicine",
                            patient_name=pat_prof.get("full_name") or "Patient",
                        )
            except HTTPException:
                raise
            except Exception:
                pass

        appt = db_store.get_appointment_by_id(appointment_id)
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment with ID '{appointment_id}' not found",
            )

        if app_role == "doctor":
            doc = db_store.get_doctor_by_profile_id(profile_id)
            if not doc or appt["doctor_id"] != doc["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You do not have access to this appointment",
                )
        else:
            patient = db_store.get_or_create_patient(profile_id=profile_id)
            if appt["patient_id"] != patient["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You do not have access to another patient's appointment",
                )

        return AppointmentResponse(**appt)

    @staticmethod
    def create_appointment(
        payload: AppointmentCreate,
        current_user: Dict[str, Any]
    ) -> AppointmentResponse:
        profile_id = current_user.get("id")

        # 1. Resolve / Ensure Patient record
        patient = None
        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                }
                with httpx.Client(timeout=5.0) as client:
                    p_res = client.get(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/patients?profile_id=eq.{profile_id}&select=id",
                        headers=headers
                    )
                    if p_res.status_code == 200 and p_res.json():
                        patient = p_res.json()[0]
                    else:
                        client.post(
                            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/patients",
                            headers=headers,
                            json={"profile_id": profile_id}
                        )
                        get_p = client.get(
                            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/patients?profile_id=eq.{profile_id}&select=id",
                            headers=headers
                        )
                        if get_p.status_code == 200 and get_p.json():
                            patient = get_p.json()[0]
            except Exception as e:
                print(f"Supabase patient resolution error: {e}")

        if not patient:
            patient = db_store.get_or_create_patient(
                profile_id=profile_id,
                full_name=current_user.get("full_name", "Patient"),
                email=current_user.get("email"),
            )

        # 2. Validate Doctor exists and is active
        doc = db_store.get_doctor_by_id(payload.doctor_id)
        if not doc or not doc.get("is_active", True):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Doctor with ID '{payload.doctor_id}' not found or is currently inactive",
            )

        # 3. Validate Date format and logical constraints
        try:
            appt_date_obj = datetime.strptime(payload.appointment_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="appointment_date must be in YYYY-MM-DD format",
            )

        # 4. Validate start_time and end_time
        try:
            start_t = parse_time_str(payload.start_time)
            end_t = parse_time_str(payload.end_time)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

        if start_t >= end_t:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="start_time must be strictly earlier than end_time",
            )

        # 5. Validate slot falls within Doctor's active availability for that day
        db_day = get_db_day_of_week(appt_date_obj)
        doctor_slots = db_store.get_doctor_availability(payload.doctor_id, only_active=True)
        
        is_available = False
        for slot in doctor_slots:
            if slot["day_of_week"] == db_day:
                slot_start = parse_time_str(slot["start_time"])
                slot_end = parse_time_str(slot["end_time"])
                if start_t >= slot_start and end_t <= slot_end:
                    is_available = True
                    break

        if not is_available:
            day_name = DAY_NAMES.get(db_day, "that day")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Requested time ({payload.start_time} - {payload.end_time}) on {day_name} ({payload.appointment_date}) falls outside doctor's active schedule.",
            )

        # 6. Check for double booking / overlapping conflicts
        conflict_msg = db_store.check_conflict(
            doctor_id=payload.doctor_id,
            patient_id=patient["id"],
            appt_date=payload.appointment_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
        if conflict_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=conflict_msg,
            )

        # 7. Create Appointment in Supabase if configured
        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                    "Prefer": "return=representation"
                }
                with httpx.Client(timeout=5.0) as client:
                    res = client.post(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments",
                        headers=headers,
                        json={
                            "patient_id": patient["id"],
                            "doctor_id": payload.doctor_id,
                            "appointment_date": payload.appointment_date,
                            "start_time": payload.start_time,
                            "end_time": payload.end_time,
                            "reason": payload.reason,
                            "status": "scheduled",
                        }
                    )
                    if res.status_code in (200, 201) and res.json():
                        new_a = res.json()[0]
                        db_store.appointments[new_a["id"]] = new_a
                        return AppointmentResponse(
                            id=new_a["id"],
                            patient_id=new_a["patient_id"],
                            doctor_id=new_a["doctor_id"],
                            appointment_date=str(new_a["appointment_date"]),
                            start_time=str(new_a["start_time"]),
                            end_time=str(new_a["end_time"]),
                            reason=new_a.get("reason"),
                            status=new_a.get("status", "scheduled"),
                            notes=new_a.get("notes"),
                            created_at=new_a.get("created_at"),
                            updated_at=new_a.get("updated_at"),
                            doctor_name=doc["full_name"] if doc else "Doctor",
                            doctor_specialty=doc["specialty"] if doc else "General",
                            patient_name=current_user.get("full_name", "Patient"),
                        )
            except Exception as e:
                print(f"Supabase appointment insert error: {e}")

        # Local db_store fallback
        created = db_store.create_appointment(
            patient_id=patient["id"],
            doctor_id=payload.doctor_id,
            appt_date=payload.appointment_date,
            start_time=payload.start_time,
            end_time=payload.end_time,
            reason=payload.reason,
        )

        return AppointmentResponse(**created)

    @staticmethod
    def cancel_appointment(
        appointment_id: str,
        current_user: Dict[str, Any]
    ) -> AppointmentResponse:
        profile_id = current_user.get("id")
        app_role = current_user.get("app_role", "patient")

        if settings.SUPABASE_URL:
            try:
                profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
                headers = {
                    "apikey": profile_key,
                    "Authorization": f"Bearer {profile_key}",
                    "Prefer": "return=representation"
                }
                with httpx.Client(timeout=5.0) as client:
                    client.patch(
                        f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments?id=eq.{appointment_id}",
                        headers=headers,
                        json={"status": "cancelled"}
                    )
            except Exception:
                pass

        appt = db_store.get_appointment_by_id(appointment_id)
        if not appt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Appointment with ID '{appointment_id}' not found",
            )

        if app_role == "doctor":
            doc = db_store.get_doctor_by_profile_id(profile_id)
            if not doc or appt["doctor_id"] != doc["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You cannot modify an appointment not assigned to you",
                )
        else:
            patient = db_store.get_or_create_patient(profile_id=profile_id)
            if appt["patient_id"] != patient["id"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized: You cannot modify another patient's appointment",
                )

        updated = db_store.cancel_appointment(appointment_id)
        return AppointmentResponse(**updated)


appointment_service = AppointmentService()
