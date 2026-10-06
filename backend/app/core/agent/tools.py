import logging
import httpx
from datetime import datetime, timedelta, time
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.services.data_store import (
    db_store,
    parse_time_str,
    format_time_str,
    get_db_day_of_week,
    DAY_NAMES,
)
from app.services.doctor_service import doctor_service
from app.services.appointment_service import appointment_service
from app.schemas.appointment import AppointmentCreate

logger = logging.getLogger(__name__)

AGENT_TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_doctors",
            "description": "Search active doctors by medical specialty, doctor name, or maximum consultation fee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {
                        "type": "string",
                        "description": "Medical specialty (e.g., 'Cardiology', 'Neurology', 'Pediatrics', 'General Medicine', 'Orthopedics').",
                    },
                    "name": {
                        "type": "string",
                        "description": "Doctor's name or partial name (e.g. 'Sarah', 'Jenkins', 'Vance', 'Bidhan').",
                    },
                    "max_fee": {
                        "type": "number",
                        "description": "Maximum consultation fee in dollars.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doctor_details",
            "description": "Get comprehensive profile, qualifications, clinic address, contact info, consultation fee, and demonstration reviews for a specific doctor ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor.",
                    },
                },
                "required": ["doctor_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check real-time available 30-minute booking time slots for a doctor on a specific date (YYYY-MM-DD).",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor.",
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "Target date in YYYY-MM-DD format (e.g., '2026-10-05').",
                    },
                },
                "required": ["doctor_id", "appointment_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_appointments",
            "description": "Retrieve current and upcoming appointments for the authenticated patient.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment belonging to the authenticated patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "The unique ID of the appointment to cancel.",
                    },
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "prepare_booking_confirmation",
            "description": "Prepare and validate appointment details before booking. Returns formatted doctor name, date, time slot, fee, and clinic details to present to the patient for their explicit confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor.",
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format.",
                    },
                    "appointment_time": {
                        "type": "string",
                        "description": "Slot start time in HH:MM (24-hour) format (e.g., '09:00', '14:30').",
                    },
                    "consultation_type": {
                        "type": "string",
                        "enum": ["in_person", "telehealth"],
                        "description": "Type of consultation.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Reason or clinical notes for the appointment.",
                    },
                },
                "required": ["doctor_id", "appointment_date", "appointment_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Confirm and book an appointment after the patient has explicitly confirmed the doctor, date, and time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctor_id": {
                        "type": "string",
                        "description": "The unique ID of the doctor.",
                    },
                    "appointment_date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format.",
                    },
                    "appointment_time": {
                        "type": "string",
                        "description": "Slot start time in HH:MM format (e.g. '09:00').",
                    },
                    "consultation_type": {
                        "type": "string",
                        "enum": ["in_person", "telehealth"],
                        "description": "Type of consultation (default: 'in_person').",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Reason or clinical notes for the appointment.",
                    },
                    "confirmed": {
                        "type": "boolean",
                        "description": "MUST be true. The patient must have explicitly approved booking this specific slot.",
                    },
                },
                "required": ["doctor_id", "appointment_date", "appointment_time", "confirmed"],
            },
        },
    },
]


def _compute_available_slots(doctor_id: str, date_str: str) -> Dict[str, Any]:
    """Helper to calculate available 30-minute slots on a date for a doctor."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return {"error": f"Invalid date format '{date_str}'. Please use YYYY-MM-DD."}

    try:
        doc_res = doctor_service.get_doctor_by_id(doctor_id)
        doc = doc_res.model_dump() if hasattr(doc_res, "model_dump") else doc_res
    except Exception:
        doc = db_store.get_doctor_by_id(doctor_id)

    if not doc:
        return {"error": f"Doctor with ID '{doctor_id}' was not found."}

    day_of_week = get_db_day_of_week(dt)
    day_name = DAY_NAMES.get(day_of_week, "Unknown")

    # Get doctor's weekly active schedule
    try:
        all_schedules_res = doctor_service.get_doctor_availability(doctor_id)
        all_schedules = [s.model_dump() if hasattr(s, "model_dump") else s for s in all_schedules_res]
    except Exception:
        all_schedules = db_store.get_doctor_availability(doctor_id, only_active=True)

    matching_schedules = [s for s in all_schedules if s["day_of_week"] == day_of_week and s.get("is_active", True)]

    if not matching_schedules:
        return {
            "doctor_id": doctor_id,
            "doctor_name": doc.get("full_name"),
            "date": date_str,
            "day_of_week": day_name,
            "available_slots": [],
            "message": f"{doc.get('full_name')} is not scheduled for consultations on {day_name}s.",
        }

    # Get doctor's existing appointments for this date
    doctor_appts = []
    if settings.SUPABASE_URL:
        try:
            profile_key = settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
            headers = {"apikey": profile_key, "Authorization": f"Bearer {profile_key}"}
            with httpx.Client(timeout=3.0) as client:
                res = client.get(
                    f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/appointments?doctor_id=eq.{doctor_id}&appointment_date=eq.{date_str}&status=neq.cancelled&select=start_time,end_time",
                    headers=headers
                )
                if res.status_code == 200 and isinstance(res.json(), list):
                    for a in res.json():
                        doctor_appts.append({
                            "start_time": format_time_str(a["start_time"]),
                            "end_time": format_time_str(a["end_time"]),
                        })
        except Exception:
            pass

    for a in db_store.appointments.values():
        if a["doctor_id"] == doctor_id and a["appointment_date"] == date_str and a.get("status") != "cancelled":
            doctor_appts.append({
                "start_time": format_time_str(a["start_time"]),
                "end_time": format_time_str(a["end_time"]),
            })

    available_slots = []

    for sched in matching_schedules:
        s_start = parse_time_str(sched["start_time"])
        s_end = parse_time_str(sched["end_time"])

        curr_time = datetime.combine(dt, s_start)
        end_dt = datetime.combine(dt, s_end)

        while curr_time + timedelta(minutes=30) <= end_dt:
            slot_start_str = curr_time.strftime("%H:%M")
            slot_end_dt = curr_time + timedelta(minutes=30)
            slot_end_str = slot_end_dt.strftime("%H:%M")

            # Check overlap with existing appointments
            conflict = False
            for appt in doctor_appts:
                a_start = parse_time_str(appt["start_time"])
                a_end = parse_time_str(appt["end_time"])
                if not (slot_end_dt.time() <= a_start or curr_time.time() >= a_end):
                    conflict = True
                    break

            if not conflict:
                available_slots.append({
                    "start_time": slot_start_str,
                    "end_time": slot_end_str,
                    "display": f"{slot_start_str} - {slot_end_str}",
                })

            curr_time += timedelta(minutes=30)

    return {
        "doctor_id": doctor_id,
        "doctor_name": doc.get("full_name"),
        "specialty": doc.get("specialty"),
        "consultation_fee": doc.get("consultation_fee"),
        "date": date_str,
        "day_of_week": day_name,
        "available_slots": available_slots,
        "total_available": len(available_slots),
    }


def execute_tool(
    name: str,
    args: Dict[str, Any],
    current_user: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute tool server-side using existing services and live data.
    Security: The authenticated `current_user` session is injected and enforced.
    """
    logger.info(f"Executing agent tool: {name} with args: {args}")

    try:
        if name == "search_doctors":
            specialty = (args.get("specialty") or "").lower().strip()
            query_name = (args.get("name") or "").lower().strip()
            max_fee = args.get("max_fee")

            try:
                all_docs_res = doctor_service.get_all_active_doctors()
                all_docs = [d.model_dump() if hasattr(d, "model_dump") else d for d in all_docs_res]
            except Exception:
                all_docs = db_store.get_all_active_doctors()

            filtered = []
            for d in all_docs:
                if specialty and specialty not in (d.get("specialty") or "").lower():
                    continue
                if query_name and query_name not in (d.get("full_name") or "").lower():
                    continue
                if max_fee is not None and d.get("consultation_fee") is not None:
                    if float(d.get("consultation_fee")) > float(max_fee):
                        continue
                filtered.append({
                    "id": d["id"],
                    "full_name": d["full_name"],
                    "specialty": d.get("specialty"),
                    "qualification": d.get("qualification"),
                    "experience_years": d.get("experience_years"),
                    "consultation_fee": d.get("consultation_fee"),
                    "clinic_address": d.get("clinic_address"),
                    "rating": d.get("rating"),
                    "reviews_count": d.get("reviews_count"),
                })

            return {
                "count": len(filtered),
                "doctors": filtered,
                "query": {"specialty": specialty, "name": query_name, "max_fee": max_fee},
            }

        elif name == "get_doctor_details":
            doctor_id = args.get("doctor_id")
            if not doctor_id:
                return {"error": "doctor_id is required."}

            try:
                doc_res = doctor_service.get_doctor_by_id(doctor_id)
                doc = doc_res.model_dump() if hasattr(doc_res, "model_dump") else doc_res
            except Exception:
                doc = db_store.get_doctor_by_id(doctor_id)

            if not doc:
                return {"error": f"Doctor with ID '{doctor_id}' not found."}
            
            # Fetch weekly availability summary
            try:
                avail_res = doctor_service.get_doctor_availability(doctor_id)
                avail = [s.model_dump() if hasattr(s, "model_dump") else s for s in avail_res]
            except Exception:
                avail = db_store.get_doctor_availability(doctor_id, only_active=True)

            schedule_summary = [
                f"{s.get('day_name')}: {s.get('start_time')} - {s.get('end_time')}"
                for s in avail
            ]

            return {
                "doctor": doc,
                "weekly_schedule": schedule_summary,
                "demo_reviews": doc.get("demo_reviews", []),
            }

        elif name == "check_doctor_availability":
            doctor_id = args.get("doctor_id")
            appointment_date = args.get("appointment_date")
            if not doctor_id or not appointment_date:
                return {"error": "Both doctor_id and appointment_date are required."}
            return _compute_available_slots(doctor_id, appointment_date)

        elif name == "get_my_appointments":
            appts = appointment_service.get_user_appointments(current_user)
            return {
                "count": len(appts),
                "appointments": [a.model_dump() for a in appts],
            }

        elif name == "cancel_appointment":
            appointment_id = args.get("appointment_id")
            if not appointment_id:
                return {"error": "appointment_id is required."}
            cancelled = appointment_service.cancel_appointment(appointment_id, current_user)
            return {
                "success": True,
                "message": "Appointment cancelled successfully.",
                "appointment": cancelled.model_dump(),
            }

        elif name == "prepare_booking_confirmation":
            doctor_id = args.get("doctor_id")
            appt_date = args.get("appointment_date")
            appt_time = args.get("appointment_time")
            consultation_type = args.get("consultation_type", "in_person")
            notes = args.get("notes", "")

            if not doctor_id or not appt_date or not appt_time:
                return {"error": "doctor_id, appointment_date, and appointment_time are required."}

            try:
                doc_res = doctor_service.get_doctor_by_id(doctor_id)
                doc = doc_res.model_dump() if hasattr(doc_res, "model_dump") else doc_res
            except Exception:
                doc = db_store.get_doctor_by_id(doctor_id)

            if not doc:
                return {"error": f"Doctor '{doctor_id}' not found."}

            # Normalize appointment time
            t_obj = parse_time_str(appt_time)
            start_str = t_obj.strftime("%H:%M")
            end_dt = (datetime.combine(datetime.today(), t_obj) + timedelta(minutes=30)).time()
            end_str = end_dt.strftime("%H:%M")

            # Check slot availability
            avail_data = _compute_available_slots(doctor_id, appt_date)
            if "error" in avail_data:
                return avail_data

            slots = [s["start_time"] for s in avail_data.get("available_slots", [])]
            if start_str not in slots:
                return {
                    "status": "slot_unavailable",
                    "message": f"The slot at {start_str} on {appt_date} is not available for {doc.get('full_name')}.",
                    "available_slots": avail_data.get("available_slots", []),
                }

            return {
                "status": "ready_for_confirmation",
                "confirmation_details": {
                    "doctor_id": doctor_id,
                    "doctor_name": doc.get("full_name"),
                    "specialty": doc.get("specialty"),
                    "clinic_address": doc.get("clinic_address"),
                    "contact_phone": doc.get("contact_phone"),
                    "consultation_fee": doc.get("consultation_fee"),
                    "appointment_date": appt_date,
                    "appointment_time": start_str,
                    "end_time": end_str,
                    "consultation_type": consultation_type,
                    "notes": notes,
                },
                "instructions": (
                    "Present these exact details to the patient and ask them explicitly: "
                    f"'Would you like me to confirm and book your appointment with {doc.get('full_name')} on {appt_date} at {start_str}?'"
                ),
            }

        elif name == "book_appointment":
            doctor_id = args.get("doctor_id")
            appt_date = args.get("appointment_date")
            appt_time = args.get("appointment_time")
            consultation_type = args.get("consultation_type", "in_person")
            notes = args.get("notes", "")
            confirmed = args.get("confirmed", False)

            if not confirmed:
                return {
                    "status": "confirmation_required",
                    "error": "Booking rejected: Patient has not explicitly confirmed this appointment slot. Please present the doctor, date, and time and ask for confirmation first.",
                }

            if not doctor_id or not appt_date or not appt_time:
                return {"error": "doctor_id, appointment_date, and appointment_time are required."}

            t_obj = parse_time_str(appt_time)
            start_str = t_obj.strftime("%H:%M")
            end_dt = (datetime.combine(datetime.today(), t_obj) + timedelta(minutes=30)).time()
            end_str = end_dt.strftime("%H:%M")

            reason_str = f"[{consultation_type.upper()}] {notes}".strip() if notes else f"[{consultation_type.upper()}] General Consultation"

            payload = AppointmentCreate(
                doctor_id=doctor_id,
                appointment_date=appt_date,
                start_time=start_str,
                end_time=end_str,
                reason=reason_str,
            )

            # Delegate to existing appointment service for authentication & double-booking protection
            created = appointment_service.create_appointment(payload, current_user)
            try:
                doc_res = doctor_service.get_doctor_by_id(doctor_id)
                doc = doc_res.model_dump() if hasattr(doc_res, "model_dump") else doc_res
            except Exception:
                doc = db_store.get_doctor_by_id(doctor_id)

            return {
                "status": "booking_success",
                "message": f"Appointment successfully booked with {doc.get('full_name') if doc else 'Doctor'} on {appt_date} at {start_str}.",
                "appointment": created.model_dump(),
                "doctor": doc,
            }

        else:
            return {"error": f"Unknown tool: {name}"}

    except Exception as e:
        logger.error(f"Error executing agent tool {name}: {str(e)}", exc_info=True)
        return {"error": f"Tool execution failed: {str(e)}"}

