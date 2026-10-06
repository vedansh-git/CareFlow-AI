# CareFlow AI — Step 3A: Doctor Profiles, Availability & Appointments Guide

## 1. Overview
Step 3A establishes the **deterministic, non-AI clinical appointment and scheduling engine** for CareFlow AI. Before introducing LLMs, speech-to-text, or multi-agent workflows, healthcare systems require rock-solid database integrity, deterministic time-slot validation, and double-booking prevention.

---

## 2. Database Schema Design

### 2.1 Doctor Availability (`public.doctor_availability`)
Stores recurring weekly consultation schedules for each doctor.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID PK` | Auto-generated unique identifier |
| `doctor_id` | `UUID FK` | References `public.doctors(id)` ON DELETE CASCADE |
| `day_of_week` | `INTEGER` | 0 = Sunday, 1 = Monday, 2 = Tuesday, 3 = Wednesday, 4 = Thursday, 5 = Friday, 6 = Saturday |
| `start_time` | `TIME` | Consultation start time (e.g., `09:00`) |
| `end_time` | `TIME` | Consultation end time (e.g., `17:00`) |
| `is_active` | `BOOLEAN` | Whether this schedule slot is active |
| `created_at` | `TIMESTAMPTZ` | Timestamp of slot creation |

**Integrity Constraints:**
- `CHECK (start_time < end_time)`
- `CHECK (day_of_week >= 0 AND day_of_week <= 6)`
- `UNIQUE (doctor_id, day_of_week, start_time, end_time)`

---

### 2.2 Appointments (`public.appointments`)
Tracks clinical consultations booked between patients and physicians.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `UUID PK` | Unique appointment identifier |
| `patient_id` | `UUID FK` | References `public.patients(id)` ON DELETE CASCADE |
| `doctor_id` | `UUID FK` | References `public.doctors(id)` ON DELETE CASCADE |
| `appointment_date`| `DATE` | Scheduled consultation date (`YYYY-MM-DD`) |
| `start_time` | `TIME` | Start time of consultation slot (e.g., `10:00`) |
| `end_time` | `TIME` | End time of consultation slot (e.g., `10:30`) |
| `reason` | `TEXT` | Chief complaint / consultation reason |
| `status` | `ENUM` | `'scheduled'`, `'completed'`, `'cancelled'`, `'no_show'` |
| `notes` | `TEXT` | Clinical consultation notes |
| `created_at` | `TIMESTAMPTZ` | Time of booking |
| `updated_at` | `TIMESTAMPTZ` | Auto-updated via trigger |

---

## 3. Database-Level Double-Booking Prevention

To guarantee zero race conditions or accidental overlapping slots, double-booking is prevented **at the database level** using PostgreSQL partial unique indexes:

```sql
-- 1. Prevent overlapping bookings for the same doctor on the same date/time
CREATE UNIQUE INDEX idx_no_doctor_double_booking
    ON public.appointments (doctor_id, appointment_date, start_time)
    WHERE status != 'cancelled';

-- 2. Prevent a patient from booking multiple overlapping appointments at the same date/time
CREATE UNIQUE INDEX idx_no_patient_double_booking
    ON public.appointments (patient_id, appointment_date, start_time)
    WHERE status != 'cancelled';
```

When an appointment is cancelled, its status changes to `'cancelled'`, which automatically frees up the time slot for other patients.

---

## 4. Row Level Security (RLS) Policies

All tables have RLS enabled:

- **Patients:**
  - Can view all active doctor profiles and their active weekly availability.
  - Can create appointments **only** for their own patient profile.
  - Can view and cancel **only** their own appointments.
  - Cannot access or tamper with other patients' medical records or appointments.
- **Doctors:**
  - Can view and manage (create/update/delete) their own availability hours.
  - Can view all appointments assigned to them.
  - Can update appointment status and notes for their consultations.

---

## 5. API Endpoints Reference

### Public / Authenticated Specialist APIs
- `GET /api/doctors` — List all active physicians.
- `GET /api/doctors/{doctor_id}` — Get single doctor profile.
- `GET /api/doctors/{doctor_id}/availability` — Get doctor's active weekly consultation schedule.

### Appointment Booking APIs
- `GET /api/appointments` — List appointments for current authenticated user (patient or doctor).
- `POST /api/appointments` — Book a new appointment (validates doctor schedule, availability, and conflicts).
- `GET /api/appointments/{appointment_id}` — Get detailed appointment record (ownership checked).
- `PATCH /api/appointments/{appointment_id}/cancel` — Cancel an active scheduled appointment.

### Doctor Self-Management APIs
- `GET /api/doctor/me` — Retrieve logged-in doctor profile.
- `GET /api/doctor/me/availability` — View all availability slots for logged-in doctor.
- `POST /api/doctor/me/availability` — Add new working hours slot.
- `PUT /api/doctor/me/availability/{availability_id}` — Update working hours.
- `DELETE /api/doctor/me/availability/{availability_id}` — Remove working hours.

---

## 6. Safe Test Doctor Creation Guide

Because self-registration via UI is strictly restricted to `role = 'patient'`, follow this safe procedure to create a doctor account for testing:

1. Register a new user in the application UI (e.g. `doctor.test@careflow.ai`).
2. Copy the user's UUID from Supabase Dashboard $\rightarrow$ **Authentication** $\rightarrow$ **Users**.
3. Open Supabase **SQL Editor** and run:
```sql
-- 1. Upgrade the profile role to doctor
UPDATE public.profiles
SET role = 'doctor'::public.user_role,
    full_name = 'Dr. Test Physician'
WHERE id = '<USER_UUID>';

-- 2. Insert corresponding doctor record
INSERT INTO public.doctors (profile_id, specialty, qualification, bio, is_active)
VALUES (
    '<USER_UUID>',
    'Cardiology',
    'MD, FACC - Harvard Medical',
    'Specialist in cardiovascular healthcare.',
    TRUE
)
ON CONFLICT (profile_id) DO UPDATE
SET specialty = EXCLUDED.specialty,
    qualification = EXCLUDED.qualification,
    bio = EXCLUDED.bio;

-- 3. Add default weekly working hours (Monday to Friday 09:00 - 17:00)
INSERT INTO public.doctor_availability (doctor_id, day_of_week, start_time, end_time, is_active)
SELECT id, day_num, '09:00'::TIME, '17:00'::TIME, TRUE
FROM public.doctors, generate_series(1, 5) AS day_num
WHERE profile_id = '<USER_UUID>';
```
