-- ============================================================
-- CareFlow AI - Fix Table Permissions & Ensure RLS Security
-- ============================================================
-- PURPOSE:
--   PostgreSQL requires table-level GRANTs for roles (authenticated/anon)
--   in addition to Row Level Security (RLS) policies.
--   Without GRANT SELECT ON TABLE public.profiles TO authenticated,
--   PostgreSQL raises error 42501 (permission denied for table profiles).
--
-- SECURITY:
--   - RLS remains strictly ENABLED on all tables.
--   - Role protection triggers remain strictly ENFORCED.
--   - Only authenticated users can access their own rows via RLS.
-- ============================================================

-- 1. Ensure Schema Usage
GRANT USAGE ON SCHEMA public TO anon, authenticated;

-- 2. Profiles Table Permissions & RLS
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

GRANT SELECT, UPDATE ON TABLE public.profiles TO authenticated;

DROP POLICY IF EXISTS "Users can read own profile" ON public.profiles;
CREATE POLICY "Users can read own profile"
ON public.profiles
FOR SELECT
TO authenticated
USING (
    auth.uid() = id OR role = 'doctor'
);

DROP POLICY IF EXISTS "Users can update own profile" ON public.profiles;
CREATE POLICY "Users can update own profile"
ON public.profiles
FOR UPDATE
TO authenticated
USING (
    auth.uid() = id
)
WITH CHECK (
    auth.uid() = id
);

-- 3. Patients Table Permissions & RLS
ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;

GRANT SELECT, UPDATE ON TABLE public.patients TO authenticated;

DROP POLICY IF EXISTS "Patients can read own record" ON public.patients;
CREATE POLICY "Patients can read own record"
ON public.patients
FOR SELECT
TO authenticated
USING (
    auth.uid() = profile_id
);

DROP POLICY IF EXISTS "Patients can update own record" ON public.patients;
CREATE POLICY "Patients can update own record"
ON public.patients
FOR UPDATE
TO authenticated
USING (
    auth.uid() = profile_id
)
WITH CHECK (
    auth.uid() = profile_id
);

-- 4. Doctors Table Permissions & RLS
ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;

GRANT SELECT, UPDATE ON TABLE public.doctors TO authenticated;

DROP POLICY IF EXISTS "Authenticated users can view active doctors" ON public.doctors;
CREATE POLICY "Authenticated users can view active doctors"
ON public.doctors
FOR SELECT
TO authenticated
USING (
    is_active = TRUE
);

DROP POLICY IF EXISTS "Doctors can update own profile" ON public.doctors;
CREATE POLICY "Doctors can update own profile"
ON public.doctors
FOR UPDATE
TO authenticated
USING (
    auth.uid() = profile_id
)
WITH CHECK (
    auth.uid() = profile_id
);

-- 5. Doctor Availability Permissions & RLS
ALTER TABLE public.doctor_availability ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.doctor_availability TO authenticated;

DROP POLICY IF EXISTS "Authenticated users can view active availability" ON public.doctor_availability;
CREATE POLICY "Authenticated users can view active availability"
ON public.doctor_availability
FOR SELECT
TO authenticated
USING (
    is_active = TRUE
);

DROP POLICY IF EXISTS "Doctors can manage own availability" ON public.doctor_availability;
CREATE POLICY "Doctors can manage own availability"
ON public.doctor_availability
FOR ALL
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

-- 6. Appointments Permissions & RLS
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE ON TABLE public.appointments TO authenticated;

DROP POLICY IF EXISTS "Patients can view own appointments" ON public.appointments;
CREATE POLICY "Patients can view own appointments"
ON public.appointments
FOR SELECT
TO authenticated
USING (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Patients can create appointments for themselves" ON public.appointments;
CREATE POLICY "Patients can create appointments for themselves"
ON public.appointments
FOR INSERT
TO authenticated
WITH CHECK (
    patient_id IN (
        SELECT id FROM public.patients WHERE profile_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Patients can cancel own appointments" ON public.appointments;
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

DROP POLICY IF EXISTS "Doctors can view assigned appointments" ON public.appointments;
CREATE POLICY "Doctors can view assigned appointments"
ON public.appointments
FOR SELECT
TO authenticated
USING (
    doctor_id IN (
        SELECT id FROM public.doctors WHERE profile_id = auth.uid()
    )
);

DROP POLICY IF EXISTS "Doctors can update assigned appointments" ON public.appointments;
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
