-- ============================================================
-- CareFlow AI - Step 6 Database Migration
-- Clinical Documentation, Audio Transcription & SOAP Notes
-- Supabase PostgreSQL Schema
-- ============================================================

-- 1. NOTE STATUS ENUM
DO $$
BEGIN
    CREATE TYPE public.clinical_note_status AS ENUM (
        'draft',
        'reviewed',
        'approved'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;


-- ============================================================
-- 2. CLINICAL NOTES TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS public.clinical_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    doctor_id UUID NOT NULL
        REFERENCES public.doctors(id)
        ON DELETE CASCADE,

    patient_id UUID NOT NULL
        REFERENCES public.patients(id)
        ON DELETE CASCADE,

    appointment_id UUID
        REFERENCES public.appointments(id)
        ON DELETE SET NULL,

    transcript TEXT NOT NULL,

    subjective TEXT NOT NULL DEFAULT 'Not documented',

    objective TEXT NOT NULL DEFAULT 'Not documented',

    assessment TEXT NOT NULL DEFAULT 'Not documented',

    plan TEXT NOT NULL DEFAULT 'Not documented',

    status public.clinical_note_status NOT NULL DEFAULT 'draft',

    reviewed_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================
-- 3. INDEXES FOR HIGH-PERFORMANCE LOOKUPS
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_clinical_notes_doctor_id
    ON public.clinical_notes(doctor_id);

CREATE INDEX IF NOT EXISTS idx_clinical_notes_patient_id
    ON public.clinical_notes(patient_id);

CREATE INDEX IF NOT EXISTS idx_clinical_notes_appointment_id
    ON public.clinical_notes(appointment_id);

CREATE INDEX IF NOT EXISTS idx_clinical_notes_status
    ON public.clinical_notes(status);


-- ============================================================
-- 4. TRIGGER: UPDATE updated_at
-- ============================================================

DROP TRIGGER IF EXISTS clinical_notes_updated_at ON public.clinical_notes;

CREATE TRIGGER clinical_notes_updated_at
    BEFORE UPDATE ON public.clinical_notes
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at();


-- ============================================================
-- 5. ROW LEVEL SECURITY (RLS)
-- ============================================================

ALTER TABLE public.clinical_notes
    ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Doctors can manage own clinical notes" ON public.clinical_notes;
DROP POLICY IF EXISTS "Patients can read approved clinical notes" ON public.clinical_notes;

-- Doctor Policy: Full CRUD for notes authored by the authenticated doctor
CREATE POLICY "Doctors can manage own clinical notes"
ON public.clinical_notes
FOR ALL
TO authenticated
USING (
    doctor_id IN (
        SELECT d.id FROM public.doctors d
        WHERE d.profile_id = auth.uid()
    )
)
WITH CHECK (
    doctor_id IN (
        SELECT d.id FROM public.doctors d
        WHERE d.profile_id = auth.uid()
    )
);

-- Patient Policy: Read-only access for reviewed or approved notes assigned to the patient
CREATE POLICY "Patients can read approved clinical notes"
ON public.clinical_notes
FOR SELECT
TO authenticated
USING (
    patient_id IN (
        SELECT p.id FROM public.patients p
        WHERE p.profile_id = auth.uid()
    )
    AND status IN ('reviewed', 'approved')
);
