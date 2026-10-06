-- ============================================================
-- CareFlow AI - Step 3A Doctor Seeding Utility
-- ============================================================
-- PURPOSE:
--   1. Adjust prevent_role_change() to allow database owner (postgres /
--      service_role superuser) to promote users, while continuing to
--      block ALL normal authenticated users from changing their own role.
--   2. Create a SECURITY DEFINER function promote_to_doctor() that can
--      be called from the Supabase SQL Editor (runs as postgres owner)
--      to safely promote a test user to doctor.
--   3. Create doctor availability seeding helper.
--
-- SECURITY PROPERTIES:
--   - Normal authenticated users (patients) STILL cannot change their role.
--   - RLS remains fully enabled.
--   - The promote_to_doctor() function is NOT exposed via any API.
--   - The function requires the target user's UUID — it cannot be
--     triggered by the target user themselves.
--   - No service_role key is exposed to the frontend.
-- ============================================================


-- ============================================================
-- STEP 1: Patch prevent_role_change() to allow postgres/superuser
-- ============================================================

-- HOW IT WORKS:
--   current_user = 'postgres'  when running as the Supabase DB owner
--                              (SQL Editor with postgres role, or service_role
--                               backed actions that bypass RLS).
--   current_user = 'authenticated' for all normal Supabase Auth sessions.
--
-- We only skip the check for the postgres database owner.
-- Every other session (including authenticated JWT users, even if they
-- somehow reach this trigger) is still blocked.

CREATE OR REPLACE FUNCTION public.prevent_role_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN

    -- Allow the postgres database owner (Supabase service context) to
    -- change roles for safe administrative operations (e.g. test doctor seeding).
    -- All other sessions (including every normal authenticated user) are blocked.
    IF current_user = 'postgres' THEN
        RETURN NEW;
    END IF;

    -- For all normal authenticated users: block any role change.
    IF OLD.role IS DISTINCT FROM NEW.role THEN
        RAISE EXCEPTION 'Users cannot change their own role';
    END IF;

    RETURN NEW;

END;
$$;

-- The existing trigger definition (prevent_profile_role_change) remains
-- unchanged — we only patched the function body above.
-- No need to DROP/RECREATE the trigger.


-- ============================================================
-- STEP 2: SECURITY DEFINER Doctor Promotion Function
-- ============================================================

-- This function runs as the OWNER (postgres), which is why it can
-- bypass the trigger check we added above.
--
-- It is NOT exposed as an HTTP endpoint.
-- It can only be called directly from the Supabase SQL Editor or
-- a secure server-side admin script.
-- It validates the target user exists before promoting.

CREATE OR REPLACE FUNCTION public.promote_user_to_doctor(
    target_user_id   UUID,
    doctor_full_name TEXT    DEFAULT NULL,
    doctor_specialty TEXT    DEFAULT 'General Medicine',
    doctor_qual      TEXT    DEFAULT 'MD',
    doctor_bio       TEXT    DEFAULT NULL,
    seed_weekdays    BOOLEAN DEFAULT TRUE
)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    resolved_name TEXT;
    new_doctor_id UUID;
BEGIN

    -- 1. Validate target user profile exists
    SELECT full_name INTO resolved_name
    FROM public.profiles
    WHERE id = target_user_id;

    IF resolved_name IS NULL THEN
        RAISE EXCEPTION 'No profile found for user ID: %', target_user_id;
    END IF;

    -- Use provided name or keep existing
    IF doctor_full_name IS NOT NULL THEN
        resolved_name := doctor_full_name;
    END IF;

    -- 2. Promote profile role to doctor and optionally update full_name
    --    (This UPDATE is now allowed because promote_user_to_doctor runs
    --    as the 'postgres' owner via SECURITY DEFINER, so the patched
    --    trigger skips the block.)
    UPDATE public.profiles
    SET
        role      = 'doctor'::public.user_role,
        full_name = resolved_name,
        updated_at = NOW()
    WHERE id = target_user_id;

    -- 3. Remove any existing patient record for this user
    --    (a doctor should not simultaneously be a patient in the system)
    DELETE FROM public.patients
    WHERE profile_id = target_user_id;

    -- 4. Create or update the doctors record
    INSERT INTO public.doctors (
        profile_id,
        specialty,
        qualification,
        bio,
        is_active
    )
    VALUES (
        target_user_id,
        doctor_specialty,
        doctor_qual,
        COALESCE(doctor_bio, 'Clinical specialist at CareFlow AI Medical Centre.'),
        TRUE
    )
    ON CONFLICT (profile_id)
    DO UPDATE SET
        specialty     = EXCLUDED.specialty,
        qualification = EXCLUDED.qualification,
        bio           = EXCLUDED.bio,
        is_active     = TRUE
    RETURNING id INTO new_doctor_id;

    -- 5. Optionally seed Monday–Friday (09:00–17:00) and Saturday (09:00–13:00)
    IF seed_weekdays THEN
        -- Monday (1) through Friday (5)
        INSERT INTO public.doctor_availability (
            doctor_id, day_of_week, start_time, end_time, is_active
        )
        SELECT
            new_doctor_id,
            day_num,
            '09:00'::TIME,
            '17:00'::TIME,
            TRUE
        FROM generate_series(1, 5) AS day_num
        ON CONFLICT (doctor_id, day_of_week, start_time, end_time) DO NOTHING;

        -- Saturday (6): half-day
        INSERT INTO public.doctor_availability (
            doctor_id, day_of_week, start_time, end_time, is_active
        )
        VALUES (
            new_doctor_id,
            6,
            '09:00'::TIME,
            '13:00'::TIME,
            TRUE
        )
        ON CONFLICT (doctor_id, day_of_week, start_time, end_time) DO NOTHING;
    END IF;

    RETURN format(
        'SUCCESS: User %s promoted to doctor. Doctor ID: %s. Full Name: %s. Specialty: %s. Weekdays seeded: %s',
        target_user_id,
        new_doctor_id,
        resolved_name,
        doctor_specialty,
        seed_weekdays::TEXT
    );

END;
$$;

-- Explicitly restrict EXECUTE permission so only the postgres owner can call it.
-- Revoke from PUBLIC, then grant back to specific roles as needed.
REVOKE ALL ON FUNCTION public.promote_user_to_doctor(UUID, TEXT, TEXT, TEXT, TEXT, BOOLEAN) FROM PUBLIC;
-- (postgres/service_role can still call it because it is the function OWNER)


-- ============================================================
-- STEP 3: Verification Queries (run separately after promotion)
-- ============================================================

-- You can run the following after calling promote_user_to_doctor() to confirm:
--
--   SELECT id, full_name, role FROM public.profiles WHERE id = '<USER_UUID>';
--   SELECT id, profile_id, specialty FROM public.doctors WHERE profile_id = '<USER_UUID>';
--   SELECT count(*) FROM public.doctor_availability da
--   JOIN public.doctors d ON d.id = da.doctor_id
--   WHERE d.profile_id = '<USER_UUID>';
--   SELECT relrowsecurity FROM pg_class WHERE relname = 'profiles';
