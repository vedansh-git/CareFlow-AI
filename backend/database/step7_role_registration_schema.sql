-- ============================================================
-- CareFlow AI - Database Schema Update (Step 7)
-- Role-Based Registration & Doctor Profile Authorization
-- Supabase PostgreSQL Migration
-- ============================================================

-- 1. UPDATE TRIGGER FUNCTION: handle_new_user()
-- Supports both 'patient' and 'doctor' role selection at registration.
-- Strictly prevents unauthorized 'admin' role self-registration.
-- Automatically creates doctor record in public.doctors or patient record in public.patients.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    user_full_name TEXT;
    requested_role TEXT;
    assigned_role public.user_role;
BEGIN
    -- Extract full name from raw_user_meta_data or fallback to email prefix
    user_full_name := COALESCE(
        NULLIF(TRIM(NEW.raw_user_meta_data->>'full_name'), ''),
        split_part(COALESCE(NEW.email, ''), '@', 1),
        'User'
    );

    -- Extract requested role from user metadata
    requested_role := LOWER(COALESCE(TRIM(NEW.raw_user_meta_data->>'role'), 'patient'));

    -- Strictly sanitize role: Only 'doctor' or 'patient' allowed.
    -- Prevent admin self-registration / privilege escalation.
    IF requested_role = 'doctor' THEN
        assigned_role := 'doctor'::public.user_role;
    ELSE
        assigned_role := 'patient'::public.user_role;
    END IF;

    -- 1. Create or update profile record
    INSERT INTO public.profiles (
        id,
        full_name,
        role
    )
    VALUES (
        NEW.id,
        user_full_name,
        assigned_role
    )
    ON CONFLICT (id) DO UPDATE
    SET full_name = EXCLUDED.full_name,
        -- Preserve admin role if already set by an administrator
        role = CASE 
            WHEN public.profiles.role = 'admin' THEN 'admin'::public.user_role 
            ELSE EXCLUDED.role 
        END,
        updated_at = NOW();

    -- 2. Create role-specific record
    IF assigned_role = 'doctor' THEN
        INSERT INTO public.doctors (
            profile_id,
            specialty,
            qualification,
            bio,
            is_active
        )
        VALUES (
            NEW.id,
            COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'specialty'), ''), 'General Medicine'),
            COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'qualification'), ''), 'MD'),
            COALESCE(NULLIF(TRIM(NEW.raw_user_meta_data->>'bio'), ''), 'CareFlow AI Verified Medical Practitioner'),
            TRUE
        )
        ON CONFLICT (profile_id) DO UPDATE
        SET is_active = TRUE;
    ELSE
        INSERT INTO public.patients (
            profile_id
        )
        VALUES (
            NEW.id
        )
        ON CONFLICT (profile_id) DO NOTHING;
    END IF;

    RETURN NEW;
END;
$$;

-- 2. RE-ATTACH TRIGGER TO auth.users
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- 3. SYNC EXISTING DOCTOR PROFILES
-- Ensures any existing user account with profile role = 'doctor' has an active doctors table entry.
INSERT INTO public.doctors (profile_id, specialty, qualification, bio, is_active)
SELECT 
    p.id,
    'General Medicine',
    'MD',
    'CareFlow AI Verified Medical Practitioner',
    TRUE
FROM public.profiles p
WHERE p.role = 'doctor'
  AND NOT EXISTS (
      SELECT 1 FROM public.doctors d WHERE d.profile_id = p.id
  )
ON CONFLICT (profile_id) DO UPDATE
SET is_active = TRUE;
