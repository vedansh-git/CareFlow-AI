-- ============================================================
-- CareFlow AI - Database Schema
-- Step 2: Authentication & Database Foundation
-- Supabase PostgreSQL
-- ============================================================


-- ============================================================
-- 1. USER ROLE ENUM
-- ============================================================

DO $$
BEGIN
    CREATE TYPE public.user_role AS ENUM (
        'patient',
        'doctor',
        'admin'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================
-- 2. PROFILES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY
        REFERENCES auth.users(id)
        ON DELETE CASCADE,

    full_name TEXT NOT NULL,

    role public.user_role NOT NULL DEFAULT 'patient',

    phone TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 3. PATIENTS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    profile_id UUID UNIQUE NOT NULL
        REFERENCES public.profiles(id)
        ON DELETE CASCADE,

    date_of_birth DATE,

    gender TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 4. DOCTORS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.doctors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    profile_id UUID UNIQUE NOT NULL
        REFERENCES public.profiles(id)
        ON DELETE CASCADE,

    specialty TEXT,

    qualification TEXT,

    bio TEXT,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 5. TRIGGER: UPDATE updated_at
-- ============================================================

CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS profiles_updated_at ON public.profiles;

CREATE TRIGGER profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at();


-- ============================================================
-- 6. TRIGGER: PREVENT USERS FROM CHANGING THEIR OWN ROLE
-- ============================================================

CREATE OR REPLACE FUNCTION public.prevent_role_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    IF OLD.role IS DISTINCT FROM NEW.role THEN
        RAISE EXCEPTION 'Users cannot change their own role';
    END IF;

    RETURN NEW;

END;
$$;

DROP TRIGGER IF EXISTS prevent_profile_role_change ON public.profiles;

CREATE TRIGGER prevent_profile_role_change
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_role_change();


-- ============================================================
-- 7. AUTOMATIC PROFILE + PATIENT CREATION
-- ============================================================

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    user_full_name TEXT;
BEGIN

    user_full_name := COALESCE(
        NEW.raw_user_meta_data->>'full_name',
        split_part(COALESCE(NEW.email, ''), '@', 1),
        'User'
    );


    -- Create profile.
    -- Every normal signup starts as patient.

    INSERT INTO public.profiles (
        id,
        full_name,
        role
    )
    VALUES (
        NEW.id,
        user_full_name,
        'patient'::public.user_role
    )
    ON CONFLICT (id) DO NOTHING;


    -- Automatically create patient record.

    INSERT INTO public.patients (
        profile_id
    )
    VALUES (
        NEW.id
    )
    ON CONFLICT (profile_id) DO NOTHING;


    RETURN NEW;

END;
$$;


-- Attach trigger to Supabase Auth users.

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();


-- ============================================================
-- 8. ENABLE ROW LEVEL SECURITY
-- ============================================================

ALTER TABLE public.profiles
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.patients
    ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.doctors
    ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 9. REMOVE OLD POLICIES
-- ============================================================

DROP POLICY IF EXISTS
    "Users can read own profile"
    ON public.profiles;

DROP POLICY IF EXISTS
    "Users can update own profile"
    ON public.profiles;

DROP POLICY IF EXISTS
    "Patients can read own record"
    ON public.patients;

DROP POLICY IF EXISTS
    "Patients can update own record"
    ON public.patients;

DROP POLICY IF EXISTS
    "Authenticated users can view active doctors"
    ON public.doctors;

DROP POLICY IF EXISTS
    "Doctors can update own profile"
    ON public.doctors;


-- ============================================================
-- 10. PROFILES RLS POLICIES
-- ============================================================

-- Users can view only their own profile.

CREATE POLICY "Users can read own profile"
ON public.profiles
FOR SELECT
TO authenticated
USING (
    auth.uid() = id
);


-- Users can update only their own profile.

-- The trigger above separately prevents role changes.

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


-- ============================================================
-- 11. PATIENT RLS POLICIES
-- ============================================================

-- Patient can read only their own record.

CREATE POLICY "Patients can read own record"
ON public.patients
FOR SELECT
TO authenticated
USING (
    auth.uid() = profile_id
);


-- Patient can update only their own record.

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


-- ============================================================
-- 12. DOCTOR RLS POLICIES
-- ============================================================

-- Authenticated users can view active doctors.

CREATE POLICY "Authenticated users can view active doctors"
ON public.doctors
FOR SELECT
TO authenticated
USING (
    is_active = TRUE
);


-- Doctors can update only their own doctor record.

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


-- ============================================================
-- 13. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_profiles_role
    ON public.profiles(role);
