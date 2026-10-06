import uuid
from datetime import datetime, date, time
from typing import Dict, List, Optional, Any


DAY_NAMES = {
    0: "Sunday",
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
}


def parse_time_str(t_str: str) -> time:
    """Parses HH:MM or HH:MM:SS string to time object."""
    parts = [int(p) for p in t_str.strip().split(":")]
    if len(parts) == 2:
        return time(hour=parts[0], minute=parts[1])
    elif len(parts) >= 3:
        return time(hour=parts[0], minute=parts[1], second=parts[2])
    raise ValueError(f"Invalid time format: {t_str}")


def format_time_str(t_str: str) -> str:
    """Normalizes time string to HH:MM format."""
    t = parse_time_str(t_str)
    return f"{t.hour:02d}:{t.minute:02d}"


def get_db_day_of_week(d: date) -> int:
    """
    Converts a date to DB day_of_week:
    0 = Sunday, 1 = Monday, 2 = Tuesday, 3 = Wednesday, 4 = Thursday, 5 = Friday, 6 = Saturday.
    """
    py_weekday = d.weekday()  # 0=Monday, 6=Sunday
    return 0 if py_weekday == 6 else py_weekday + 1


class InMemoryStore:
    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.patients: Dict[str, Dict[str, Any]] = {}
        self.doctors: Dict[str, Dict[str, Any]] = {}
        self.doctor_availability: Dict[str, Dict[str, Any]] = {}
        self.appointments: Dict[str, Dict[str, Any]] = {}
        self.clinical_notes: Dict[str, Dict[str, Any]] = {}
        self.seed_initial_data()

    def seed_initial_data(self):
        self.profiles.clear()
        self.patients.clear()
        self.doctors.clear()
        self.doctor_availability.clear()
        self.appointments.clear()
        self.clinical_notes.clear()

        # Seed Doctors with rich demonstration metadata
        # All phone numbers are non-contactable 555 fictional numbers
        # All reviews are explicitly marked as is_demo=True
        doc1_profile_id = "doc-prof-sarah-jenkins"
        doc1_id = "doc-sarah-jenkins-01"
        self.profiles[doc1_profile_id] = {
            "id": doc1_profile_id,
            "full_name": "Dr. Sarah Jenkins",
            "role": "doctor",
            "email": "dr.jenkins@careflow.ai",
            "phone": "+1-555-0101",
        }
        self.doctors[doc1_id] = {
            "id": doc1_id,
            "profile_id": doc1_profile_id,
            "specialty": "Cardiology",
            "qualification": "MD, FACC - Harvard Medical School",
            "bio": "Consultant Cardiologist with 14+ years of experience in cardiovascular prevention, heart health, and lipidology.",
            "clinic_address": "CareFlow Heart & Vascular Centre, 400 Medical Plaza, Suite 4A, Boston, MA",
            "contact_phone": "+1-555-0101",
            "experience_years": 14,
            "consultation_fee": 150.0,
            "rating": 4.9,
            "reviews_count": 48,
            "demo_reviews": [
                {
                    "author": "Demonstration Patient (Cardiology)",
                    "rating": 5,
                    "comment": "Dr. Jenkins was extremely thorough with my ECG assessment and explained preventative steps clearly.",
                    "date": "2026-08-15",
                    "is_demo": True
                },
                {
                    "author": "Demonstration Patient (Consultation)",
                    "rating": 5,
                    "comment": "Attentive, professional, and took time to review my family cardiovascular history.",
                    "date": "2026-09-02",
                    "is_demo": True
                }
            ],
            "is_active": True,
        }

        doc2_profile_id = "doc-prof-marcus-vance"
        doc2_id = "doc-marcus-vance-02"
        self.profiles[doc2_profile_id] = {
            "id": doc2_profile_id,
            "full_name": "Dr. Marcus Vance",
            "role": "doctor",
            "email": "dr.vance@careflow.ai",
            "phone": "+1-555-0102",
        }
        self.doctors[doc2_id] = {
            "id": doc2_id,
            "profile_id": doc2_profile_id,
            "specialty": "Neurology",
            "qualification": "MD, PhD - Johns Hopkins University",
            "bio": "Specialist in neurological diagnostics, migraine prevention, cognitive wellness, and nerve conduction studies.",
            "clinic_address": "CareFlow Neurosciences Clinic, 750 Broadway Ave, 3rd Floor, New York, NY",
            "contact_phone": "+1-555-0102",
            "experience_years": 11,
            "consultation_fee": 175.0,
            "rating": 4.8,
            "reviews_count": 36,
            "demo_reviews": [
                {
                    "author": "Demonstration Patient (Migraine Clinic)",
                    "rating": 5,
                    "comment": "Helped diagnose the root trigger of my chronic migraines after months of discomfort.",
                    "date": "2026-07-20",
                    "is_demo": True
                },
                {
                    "author": "Demonstration Patient (Neurology)",
                    "rating": 4,
                    "comment": "Very knowledgeable and structured follow-up care plan.",
                    "date": "2026-08-28",
                    "is_demo": True
                }
            ],
            "is_active": True,
        }

        doc3_profile_id = "doc-prof-emily-chen"
        doc3_id = "doc-emily-chen-03"
        self.profiles[doc3_profile_id] = {
            "id": doc3_profile_id,
            "full_name": "Dr. Emily Chen",
            "role": "doctor",
            "email": "dr.chen@careflow.ai",
            "phone": "+1-555-0103",
        }
        self.doctors[doc3_id] = {
            "id": doc3_id,
            "profile_id": doc3_profile_id,
            "specialty": "General & Family Medicine",
            "qualification": "MBBS, MRCGP - Stanford Health Care",
            "bio": "Dedicated primary care physician providing holistic care, preventive wellness exams, and chronic condition management.",
            "clinic_address": "CareFlow Family Health Pavilion, 120 Evergreen Way, Suite 101, San Jose, CA",
            "contact_phone": "+1-555-0103",
            "experience_years": 8,
            "consultation_fee": 95.0,
            "rating": 4.95,
            "reviews_count": 62,
            "demo_reviews": [
                {
                    "author": "Demonstration Patient (Family Health)",
                    "rating": 5,
                    "comment": "Compassionate doctor who listens carefully and explains treatment options in plain terms.",
                    "date": "2026-09-10",
                    "is_demo": True
                },
                {
                    "author": "Demonstration Patient (Routine Checkup)",
                    "rating": 5,
                    "comment": "Fast scheduling and excellent bedside manner. Highly recommended for family checkups.",
                    "date": "2026-09-24",
                    "is_demo": True
                }
            ],
            "is_active": True,
        }

        # Promoted Supabase Doctor: Dr. rk singh
        doc4_profile_id = "00195447-32ad-49d2-9cd1-f12e39f11c45"
        doc4_id = "doc-rk-singh-04"
        self.profiles[doc4_profile_id] = {
            "id": doc4_profile_id,
            "full_name": "Dr. rk singh",
            "role": "doctor",
            "email": "nafiwe5434@bitproy.com",
            "phone": "+1-555-0104",
        }
        self.doctors[doc4_id] = {
            "id": doc4_id,
            "profile_id": doc4_profile_id,
            "specialty": "Internal Medicine",
            "qualification": "MBBS, MD - Senior Clinical Specialist",
            "bio": "Clinical specialist at CareFlow AI Medical Centre specializing in multi-system health reviews.",
            "clinic_address": "CareFlow Central Hospital, 100 Health Sciences Blvd, Building B, Chicago, IL",
            "contact_phone": "+1-555-0104",
            "experience_years": 16,
            "consultation_fee": 130.0,
            "rating": 4.85,
            "reviews_count": 29,
            "demo_reviews": [
                {
                    "author": "Demonstration Patient (Internal Med)",
                    "rating": 5,
                    "comment": "Accurate diagnostic plan and prompt follow-up on test findings.",
                    "date": "2026-08-11",
                    "is_demo": True
                }
            ],
            "is_active": True,
        }

        # Seed Availability Slots for all 4 doctors (Mon-Fri 09:00 - 17:00, Sat 09:00 - 13:00)
        for doc_id in [doc1_id, doc2_id, doc3_id, doc4_id]:
            # Monday (1) to Friday (5)
            for day in range(1, 6):
                slot_id = str(uuid.uuid4())
                self.doctor_availability[slot_id] = {
                    "id": slot_id,
                    "doctor_id": doc_id,
                    "day_of_week": day,
                    "start_time": "09:00",
                    "end_time": "17:00",
                    "is_active": True,
                }
            # Saturday (6)
            slot_id_sat = str(uuid.uuid4())
            self.doctor_availability[slot_id_sat] = {
                "id": slot_id_sat,
                "doctor_id": doc_id,
                "day_of_week": 6,
                "start_time": "09:00",
                "end_time": "13:00",
                "is_active": True,
            }

    # ==========================
    # Doctor queries
    # ==========================
    def _format_doctor_dict(self, doc: Dict[str, Any], prof: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": doc["id"],
            "profile_id": doc["profile_id"],
            "full_name": prof.get("full_name", "Doctor"),
            "email": prof.get("email"),
            "specialty": doc.get("specialty", "General Medicine"),
            "qualification": doc.get("qualification", "MD"),
            "bio": doc.get("bio"),
            "clinic_address": doc.get("clinic_address") or "CareFlow Medical Centre, Main Campus",
            "contact_phone": doc.get("contact_phone") or prof.get("phone") or "+1-555-0100",
            "experience_years": doc.get("experience_years") or 10,
            "consultation_fee": doc.get("consultation_fee") or 100.0,
            "rating": doc.get("rating") or 4.8,
            "reviews_count": doc.get("reviews_count") or 25,
            "demo_reviews": doc.get("demo_reviews") or [],
            "is_active": doc.get("is_active", True),
        }

    def get_all_active_doctors(self) -> List[Dict[str, Any]]:
        results = []
        for doc in self.doctors.values():
            if doc.get("is_active", True):
                prof = self.profiles.get(doc["profile_id"], {})
                results.append(self._format_doctor_dict(doc, prof))
        return results

    def get_doctor_by_id(self, doctor_id: str) -> Optional[Dict[str, Any]]:
        doc = self.doctors.get(doctor_id)
        if not doc:
            return None
        prof = self.profiles.get(doc["profile_id"], {})
        return self._format_doctor_dict(doc, prof)

    def get_doctor_by_profile_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        for doc in self.doctors.values():
            if doc["profile_id"] == profile_id:
                prof = self.profiles.get(profile_id, {})
                return self._format_doctor_dict(doc, prof)
        return None

    def create_or_update_doctor(
        self,
        profile_id: str,
        specialty: str = None,
        qualification: str = None,
        bio: str = None,
        clinic_address: str = None,
        contact_phone: str = None,
        experience_years: int = None,
        consultation_fee: float = None,
    ) -> Dict[str, Any]:
        existing = self.get_doctor_by_profile_id(profile_id)
        if existing:
            doc_id = existing["id"]
            self.doctors[doc_id].update({
                "specialty": specialty or self.doctors[doc_id].get("specialty"),
                "qualification": qualification or self.doctors[doc_id].get("qualification"),
                "bio": bio or self.doctors[doc_id].get("bio"),
                "clinic_address": clinic_address or self.doctors[doc_id].get("clinic_address"),
                "contact_phone": contact_phone or self.doctors[doc_id].get("contact_phone"),
                "experience_years": experience_years if experience_years is not None else self.doctors[doc_id].get("experience_years"),
                "consultation_fee": consultation_fee if consultation_fee is not None else self.doctors[doc_id].get("consultation_fee"),
            })
            return self.get_doctor_by_id(doc_id)
        
        doc_id = str(uuid.uuid4())
        self.doctors[doc_id] = {
            "id": doc_id,
            "profile_id": profile_id,
            "specialty": specialty or "General Medicine",
            "qualification": qualification or "MD",
            "bio": bio or "",
            "clinic_address": clinic_address or "CareFlow Medical Centre, Main Campus",
            "contact_phone": contact_phone or "+1-555-0100",
            "experience_years": experience_years or 5,
            "consultation_fee": consultation_fee or 100.0,
            "rating": 4.8,
            "reviews_count": 10,
            "demo_reviews": [],
            "is_active": True,
        }
        return self.get_doctor_by_id(doc_id)

    # ==========================
    # Availability queries
    # ==========================
    def get_doctor_availability(self, doctor_id: str, only_active: bool = True) -> List[Dict[str, Any]]:
        slots = []
        for s in self.doctor_availability.values():
            if s["doctor_id"] == doctor_id:
                if only_active and not s.get("is_active", True):
                    continue
                day = s["day_of_week"]
                slots.append({
                    "id": s["id"],
                    "doctor_id": s["doctor_id"],
                    "day_of_week": day,
                    "day_name": DAY_NAMES.get(day, "Unknown"),
                    "start_time": s["start_time"],
                    "end_time": s["end_time"],
                    "is_active": s.get("is_active", True),
                })
        # Sort by day_of_week and start_time
        slots.sort(key=lambda x: (x["day_of_week"], x["start_time"]))
        return slots

    def add_doctor_availability(self, doctor_id: str, day_of_week: int, start_time: str, end_time: str, is_active: bool = True) -> Dict[str, Any]:
        slot_id = str(uuid.uuid4())
        norm_start = format_time_str(start_time)
        norm_end = format_time_str(end_time)
        self.doctor_availability[slot_id] = {
            "id": slot_id,
            "doctor_id": doctor_id,
            "day_of_week": day_of_week,
            "start_time": norm_start,
            "end_time": norm_end,
            "is_active": is_active,
        }
        return {
            "id": slot_id,
            "doctor_id": doctor_id,
            "day_of_week": day_of_week,
            "day_name": DAY_NAMES.get(day_of_week, "Unknown"),
            "start_time": norm_start,
            "end_time": norm_end,
            "is_active": is_active,
        }

    def update_doctor_availability(self, slot_id: str, day_of_week: Optional[int] = None, start_time: Optional[str] = None, end_time: Optional[str] = None, is_active: Optional[bool] = None) -> Optional[Dict[str, Any]]:
        slot = self.doctor_availability.get(slot_id)
        if not slot:
            return None
        if day_of_week is not None:
            slot["day_of_week"] = day_of_week
        if start_time is not None:
            slot["start_time"] = format_time_str(start_time)
        if end_time is not None:
            slot["end_time"] = format_time_str(end_time)
        if is_active is not None:
            slot["is_active"] = is_active
        day = slot["day_of_week"]
        return {
            "id": slot_id,
            "doctor_id": slot["doctor_id"],
            "day_of_week": day,
            "day_name": DAY_NAMES.get(day, "Unknown"),
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "is_active": slot["is_active"],
        }

    def delete_doctor_availability(self, slot_id: str) -> bool:
        if slot_id in self.doctor_availability:
            del self.doctor_availability[slot_id]
            return True
        return False

    # ==========================
    # Patient queries
    # ==========================
    def get_or_create_patient(self, profile_id: str, full_name: str = "Patient", email: str = None) -> Dict[str, Any]:
        # Check if profile exists
        if profile_id not in self.profiles:
            self.profiles[profile_id] = {
                "id": profile_id,
                "full_name": full_name,
                "role": "patient",
                "email": email,
            }
        
        # Check patient table
        for pat in self.patients.values():
            if pat["profile_id"] == profile_id:
                return pat

        # Create new patient entry
        pat_id = str(uuid.uuid4())
        self.patients[pat_id] = {
            "id": pat_id,
            "profile_id": profile_id,
            "created_at": datetime.now().isoformat(),
        }
        return self.patients[pat_id]

    def get_patient_by_id(self, patient_id: str) -> Optional[Dict[str, Any]]:
        return self.patients.get(patient_id)

    def get_patient_by_profile_id(self, profile_id: str) -> Optional[Dict[str, Any]]:
        for pat in self.patients.values():
            if pat["profile_id"] == profile_id:
                return pat
        return None

    # ==========================
    # Appointment queries
    # ==========================
    def _format_appointment(self, appt: Dict[str, Any]) -> Dict[str, Any]:
        doctor_info = self.get_doctor_by_id(appt["doctor_id"])
        patient = self.patients.get(appt["patient_id"])
        patient_profile = self.profiles.get(patient["profile_id"]) if patient else None

        return {
            "id": appt["id"],
            "patient_id": appt["patient_id"],
            "doctor_id": appt["doctor_id"],
            "appointment_date": appt["appointment_date"],
            "start_time": appt["start_time"],
            "end_time": appt["end_time"],
            "reason": appt.get("reason"),
            "status": appt.get("status", "scheduled"),
            "notes": appt.get("notes"),
            "created_at": appt.get("created_at", datetime.now().isoformat()),
            "updated_at": appt.get("updated_at"),
            "doctor_name": doctor_info["full_name"] if doctor_info else "Doctor",
            "doctor_specialty": doctor_info["specialty"] if doctor_info else "General Medicine",
            "patient_name": patient_profile.get("full_name", "Patient") if patient_profile else "Patient",
        }

    def get_appointment_by_id(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        appt = self.appointments.get(appointment_id)
        if not appt:
            return None
        return self._format_appointment(appt)

    def get_appointments_for_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        res = []
        for appt in self.appointments.values():
            if appt["patient_id"] == patient_id:
                res.append(self._format_appointment(appt))
        res.sort(key=lambda x: (x["appointment_date"], x["start_time"]))
        return res

    def get_appointments_for_doctor(self, doctor_id: str) -> List[Dict[str, Any]]:
        res = []
        for appt in self.appointments.values():
            if appt["doctor_id"] == doctor_id:
                res.append(self._format_appointment(appt))
        res.sort(key=lambda x: (x["appointment_date"], x["start_time"]))
        return res

    def check_conflict(self, doctor_id: str, patient_id: str, appt_date: str, start_time: str, end_time: str, exclude_appointment_id: str = None) -> Optional[str]:
        """
        Returns conflict description if doctor or patient is already booked during [start_time, end_time) on appt_date.
        """
        req_start = parse_time_str(start_time)
        req_end = parse_time_str(end_time)

        for appt in self.appointments.values():
            if exclude_appointment_id and appt["id"] == exclude_appointment_id:
                continue
            if appt["status"] == "cancelled":
                continue
            if appt["appointment_date"] == appt_date:
                existing_start = parse_time_str(appt["start_time"])
                existing_end = parse_time_str(appt["end_time"])

                # Check time overlap: (StartA < EndB) and (EndA > StartB)
                if (req_start < existing_end) and (req_end > existing_start):
                    if appt["doctor_id"] == doctor_id:
                        return f"Doctor is already booked for an appointment on {appt_date} between {appt['start_time']} and {appt['end_time']}."
                    if appt["patient_id"] == patient_id:
                        return f"You already have a conflicting appointment scheduled on {appt_date} between {appt['start_time']} and {appt['end_time']}."
        return None

    def create_appointment(self, patient_id: str, doctor_id: str, appt_date: str, start_time: str, end_time: str, reason: str = None) -> Dict[str, Any]:
        appt_id = str(uuid.uuid4())
        norm_start = format_time_str(start_time)
        norm_end = format_time_str(end_time)
        now_iso = datetime.now().isoformat()

        self.appointments[appt_id] = {
            "id": appt_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "appointment_date": appt_date,
            "start_time": norm_start,
            "end_time": norm_end,
            "reason": reason,
            "status": "scheduled",
            "notes": None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        return self._format_appointment(self.appointments[appt_id])

    def cancel_appointment(self, appointment_id: str) -> Optional[Dict[str, Any]]:
        appt = self.appointments.get(appointment_id)
        if not appt:
            return None
        appt["status"] = "cancelled"
        appt["updated_at"] = datetime.now().isoformat()
        return self._format_appointment(appt)

    def _format_clinical_note(self, note: Dict[str, Any]) -> Dict[str, Any]:
        doctor_info = self.get_doctor_by_id(note["doctor_id"])
        patient = self.patients.get(note["patient_id"])
        patient_profile = self.profiles.get(patient["profile_id"]) if patient else None
        return {
            "id": note["id"],
            "doctor_id": note["doctor_id"],
            "patient_id": note["patient_id"],
            "appointment_id": note.get("appointment_id"),
            "transcript": note["transcript"],
            "subjective": note.get("subjective", "Not documented"),
            "objective": note.get("objective", "Not documented"),
            "assessment": note.get("assessment", "Not documented"),
            "plan": note.get("plan", "Not documented"),
            "status": note.get("status", "draft"),
            "reviewed_at": note.get("reviewed_at"),
            "created_at": note.get("created_at", datetime.now().isoformat()),
            "updated_at": note.get("updated_at", datetime.now().isoformat()),
            "doctor_name": doctor_info["full_name"] if doctor_info else "Doctor",
            "patient_name": patient_profile.get("full_name", "Patient") if patient_profile else "Patient",
        }

    def create_clinical_note(
        self,
        doctor_id: str,
        patient_id: str,
        transcript: str,
        subjective: str = "Not documented",
        objective: str = "Not documented",
        assessment: str = "Not documented",
        plan: str = "Not documented",
        appointment_id: Optional[str] = None,
        status: str = "draft"
    ) -> Dict[str, Any]:
        note_id = str(uuid.uuid4())
        now_iso = datetime.now().isoformat()
        self.clinical_notes[note_id] = {
            "id": note_id,
            "doctor_id": doctor_id,
            "patient_id": patient_id,
            "appointment_id": appointment_id,
            "transcript": transcript,
            "subjective": subjective,
            "objective": objective,
            "assessment": assessment,
            "plan": plan,
            "status": status,
            "reviewed_at": now_iso if status in ("reviewed", "approved") else None,
            "created_at": now_iso,
            "updated_at": now_iso,
        }
        return self._format_clinical_note(self.clinical_notes[note_id])

    def get_clinical_note_by_id(self, note_id: str) -> Optional[Dict[str, Any]]:
        note = self.clinical_notes.get(note_id)
        if not note:
            return None
        return self._format_clinical_note(note)

    def list_clinical_notes_for_doctor(
        self,
        doctor_id: str,
        patient_id: Optional[str] = None,
        appointment_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        res = []
        for note in self.clinical_notes.values():
            if note["doctor_id"] == doctor_id:
                if patient_id and note["patient_id"] != patient_id:
                    continue
                if appointment_id and note.get("appointment_id") != appointment_id:
                    continue
                res.append(self._format_clinical_note(note))
        res.sort(key=lambda x: x["created_at"], reverse=True)
        return res

    def list_clinical_notes_for_patient(self, patient_id: str) -> List[Dict[str, Any]]:
        res = []
        for note in self.clinical_notes.values():
            if note["patient_id"] == patient_id and note.get("status") in ("reviewed", "approved"):
                res.append(self._format_clinical_note(note))
        res.sort(key=lambda x: x["created_at"], reverse=True)
        return res

    def update_clinical_note(self, note_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        note = self.clinical_notes.get(note_id)
        if not note:
            return None
        now_iso = datetime.now().isoformat()
        for k, v in updates.items():
            if v is not None and k in ("transcript", "subjective", "objective", "assessment", "plan", "status", "appointment_id"):
                note[k] = v
        if note.get("status") in ("reviewed", "approved") and not note.get("reviewed_at"):
            note["reviewed_at"] = now_iso
        note["updated_at"] = now_iso
        return self._format_clinical_note(note)


# Singleton in-memory store
db_store = InMemoryStore()

