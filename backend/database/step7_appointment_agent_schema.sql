-- ============================================================================
-- CareFlow AI: Step 7 - Appointment AI Agent & Rich Doctor Profiles Migration
-- ============================================================================
-- Run this SQL in the Supabase SQL Editor.
-- This adds optional profile attributes to public.doctors and seeds demo profile information.

-- 1. Add optional profile fields to doctors table (non-breaking, nullable)
ALTER TABLE public.doctors
ADD COLUMN IF NOT EXISTS clinic_address text,
ADD COLUMN IF NOT EXISTS contact_phone text,
ADD COLUMN IF NOT EXISTS experience_years integer,
ADD COLUMN IF NOT EXISTS consultation_fee numeric(10, 2) DEFAULT 100.00,
ADD COLUMN IF NOT EXISTS rating numeric(3, 2) DEFAULT 4.80,
ADD COLUMN IF NOT EXISTS reviews_count integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS demo_reviews jsonb DEFAULT '[]'::jsonb;

-- 2. Update existing demo doctors with rich sample data (if present)
-- Note: Placeholder phone numbers (+1-555-010X) are non-contactable demonstration numbers.
-- Reviews are clearly flagged with "is_demo": true.

-- Cardiology Specialist
UPDATE public.doctors
SET 
    clinic_address = 'CareFlow Heart & Vascular Pavilion, 450 Lexington Ave, Suite 400, New York, NY',
    contact_phone = '+1-555-0101',
    experience_years = 14,
    consultation_fee = 150.00,
    rating = 4.90,
    reviews_count = 48,
    demo_reviews = '[
        {
            "author": "Demonstration Patient (Cardiology)",
            "rating": 5,
            "comment": "Dr. Jenkins was extremely thorough with my ECG assessment and explained preventative steps clearly.",
            "date": "2026-08-15",
            "is_demo": true
        },
        {
            "author": "Demonstration Patient (Consultation)",
            "rating": 5,
            "comment": "Attentive, professional, and took time to review my family cardiovascular history.",
            "date": "2026-09-02",
            "is_demo": true
        }
    ]'::jsonb
WHERE specialty ILIKE '%Cardiology%' 
   OR profile_id IN (SELECT id FROM public.profiles WHERE full_name ILIKE '%Jenkins%');

-- Neurology Specialist
UPDATE public.doctors
SET 
    clinic_address = 'CareFlow Neurosciences Clinic, 750 Broadway Ave, 3rd Floor, New York, NY',
    contact_phone = '+1-555-0102',
    experience_years = 11,
    consultation_fee = 175.00,
    rating = 4.80,
    reviews_count = 36,
    demo_reviews = '[
        {
            "author": "Demonstration Patient (Migraine Clinic)",
            "rating": 5,
            "comment": "Helped diagnose the root trigger of my chronic migraines after months of discomfort.",
            "date": "2026-07-20",
            "is_demo": true
        },
        {
            "author": "Demonstration Patient (Neurology)",
            "rating": 4,
            "comment": "Very knowledgeable and structured follow-up care plan.",
            "date": "2026-08-28",
            "is_demo": true
        }
    ]'::jsonb
WHERE specialty ILIKE '%Neurology%' 
   OR profile_id IN (SELECT id FROM public.profiles WHERE full_name ILIKE '%Vance%');

-- Pediatrics Specialist
UPDATE public.doctors
SET 
    clinic_address = 'CareFlow Children & Family Health Center, 120 Riverside Dr, New York, NY',
    contact_phone = '+1-555-0103',
    experience_years = 8,
    consultation_fee = 120.00,
    rating = 4.95,
    reviews_count = 52,
    demo_reviews = '[
        {
            "author": "Demonstration Patient (Pediatric Care)",
            "rating": 5,
            "comment": "Wonderful with children and took time to make my daughter feel safe and comfortable during the visit.",
            "date": "2026-09-10",
            "is_demo": true
        }
    ]'::jsonb
WHERE specialty ILIKE '%Pediatrics%' 
   OR profile_id IN (SELECT id FROM public.profiles WHERE full_name ILIKE '%Chen%');

-- 3. Default fallback for any newly registered or unseeded doctor
UPDATE public.doctors
SET 
    clinic_address = COALESCE(clinic_address, 'CareFlow Medical Centre, Main Health Campus, New York, NY'),
    contact_phone = COALESCE(contact_phone, '+1-555-0100'),
    experience_years = COALESCE(experience_years, 5),
    consultation_fee = COALESCE(consultation_fee, 100.00),
    rating = COALESCE(rating, 4.80),
    reviews_count = COALESCE(reviews_count, 12),
    demo_reviews = COALESCE(demo_reviews, '[]'::jsonb)
WHERE clinic_address IS NULL;
