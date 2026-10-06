-- ============================================================
-- CareFlow AI - Step 3A Database Migration
-- Doctor Profiles, Availability & Appointments Foundation
-- ============================================================

-- 1. APPOINTMENT STATUS ENUM
DO $$
BEGIN
    CREATE TYPE public.appointment_status AS ENUM (
        'scheduled',
        'completed',
        'cancelled',
        'no_show'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================
-- 2. DOCTOR AVAILABILITY TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.doctor_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    doctor_id UUID NOT NULL
        REFERENCES public.doctors(id)
        ON DELETE CASCADE,

    day_of_week INTEGER NOT NULL
        CHECK (day_of_week >= 0 AND day_of_week <= 6),
        -- 0 = Sunday, 1 = Monday, 2 = Tuesday, 3 = Wednesday, 4 = Thursday, 5 = Friday, 6 = Saturday

    start_time TIME NOT NULL,

    end_time TIME NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_availability_time_order CHECK (start_time < end_time),
    CONSTRAINT uq_doctor_day_time UNIQUE (doctor_id, day_of_week, start_time, end_time)
);


-- ============================================================
-- 3. APPOINTMENTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    patient_id UUID NOT NULL
        REFERENCES public.patients(id)
        ON DELETE CASCADE,

    doctor_id UUID NOT NULL
        REFERENCES public.doctors(id)
        ON DELETE CASCADE,

    appointment_date DATE NOT NULL,

    start_time TIME NOT NULL,

    end_time TIME NOT NULL,

    reason TEXT,

    status public.appointment_status NOT NULL DEFAULT 'scheduled',

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_appointment_time_order CHECK (start_time < end_time)
);


-- ============================================================
-- 4. DOUBLE-BOOKING PREVENTION (DATABASE LEVEL)
-- ============================================================

-- Prevent double booking the same doctor for overlapping active appointments on same date & start_time
CREATE UNIQUE INDEX IF NOT EXISTS idx_no_doctor_double_booking
    ON public.appointments (doctor_id, appointment_date, start_time)
    WHERE status != 'cancelled';

-- Prevent a patient from booking multiple overlapping appointments at the exact same date & start_time
CREATE UNIQUE INDEX IF NOT EXISTS idx_no_patient_double_booking
    ON public.appointments (patient_id, appointment_date, start_time)
    WHERE status != 'cancelled';


-- ============================================================
-- 5. INDEXES FOR PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_doctor_availability_doctor_id
    ON public.doctor_availability (doctor_id);

CREATE INDEX IF NOT EXISTS idx_doctor_availability_day
    ON public.doctor_availability (doctor_id, day_of_week);

CREATE INDEX IF NOT EXISTS idx_appointments_patient_id
    ON public.appointments (patient_id);

CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id
    ON public.appointments (doctor_id);

CREATE INDEX IF NOT EXISTS idx_appointments_date
    ON public.appointments (appointment_date);

CREATE INDEX IF NOT EXISTS idx_appointments_status
    ON public.appointments (status);


-- ============================================================
-- 6. TRIGGER FOR updated_at ON APPOINTMENTS
-- ============================================================

DROP TRIGGER IF EXISTS appointments_updated_at ON public.appointments;

CREATE TRIGGER appointments_updated_at
    BEFORE UPDATE ON public.appointments
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at();


-- ============================================================
-- 7. ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================

ALTER TABLE public.doctor_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

-- ------------------------------------------------------------
-- Doctor Availability RLS Policies
-- ------------------------------------------------------------

DROP POLICY IF EXISTS "Anyone authenticated can view active doctor availability" ON public.doctor_availability;
DROP POLICY IF EXISTS "Doctors can manage own availability" ON public.doctor_availability;

-- Authenticated users (patients and doctors) can view active doctor schedules
CREATE POLICY "Anyone authenticated can view active doctor availability"
ON public.doctor_availability
FOR SELECT
TO authenticated
USING (
    is_active = TRUE
    OR doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

-- Doctors can insert their own availability
CREATE POLICY "Doctors can insert own availability"
ON public.doctor_availability
FOR INSERT
TO authenticated
WITH CHECK (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

-- Doctors can update their own availability
CREATE POLICY "Doctors can update own availability"
ON public.doctor_availability
FOR UPDATE
TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
)
WITH CHECK (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

-- Doctors can delete their own availability
CREATE POLICY "Doctors can delete own availability"
ON public.doctor_availability
FOR DELETE
TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

-- ------------------------------------------------------------
-- Appointments RLS Policies
-- ------------------------------------------------------------

DROP POLICY IF EXISTS "Patients can view own appointments" ON public.appointments;
DROP POLICY IF EXISTS "Patients can create appointments for themselves" ON public.appointments;
DROP POLICY IF EXISTS "Patients can cancel own appointments" ON public.appointments;
DROP POLICY IF EXISTS "Doctors can view assigned appointments" ON public.appointments;
DROP POLICY IF EXISTS "Doctors can update assigned appointments" ON public.appointments;

-- 1. Patients can view only their own appointments
CREATE POLICY "Patients can view own appointments"
ON public.appointments
FOR SELECT
TO authenticated
USING (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
);

-- 2. Patients can create appointments ONLY for their own patient profile
CREATE POLICY "Patients can create appointments for themselves"
ON public.appointments
FOR INSERT
TO authenticated
WITH CHECK (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
);

-- 3. Patients can cancel only their own scheduled appointments
CREATE POLICY "Patients can cancel own appointments"
ON public.appointments
FOR UPDATE
TO authenticated
USING (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
)
WITH CHECK (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
    AND status = 'cancelled'
);

-- 4. Doctors can view appointments assigned to them
CREATE POLICY "Doctors can view assigned appointments"
ON public.appointments
FOR SELECT
TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

-- 5. Doctors can update appointments assigned to them (e.g., status, notes)
CREATE POLICY "Doctors can update assigned appointments"
ON public.appointments
FOR UPDATE
TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
)
WITH CHECK (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);
