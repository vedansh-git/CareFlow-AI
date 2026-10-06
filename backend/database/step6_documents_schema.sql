-- ============================================================
-- CareFlow AI - Document & Storage Schema Migration (Safe & Rerunnable)
-- ============================================================

-- 1. Modify clinical_documents to support ownership and files
ALTER TABLE public.clinical_documents 
    ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES auth.users(id),
    ADD COLUMN IF NOT EXISTS file_path TEXT,
    ADD COLUMN IF NOT EXISTS file_type TEXT,
    ADD COLUMN IF NOT EXISTS file_size INTEGER,
    ADD COLUMN IF NOT EXISTS is_private BOOLEAN DEFAULT TRUE;

-- Preserve existing public reference documents explicitly
-- Legacy RAG documents were ingested before file_path existed and without an owner
UPDATE public.clinical_documents 
SET is_private = false 
WHERE owner_id IS NULL 
  AND file_path IS NULL
  AND is_private = true;

-- 2. Clean up ALL existing RLS policies to prevent conflicts
DROP POLICY IF EXISTS "Anyone authenticated can read clinical_documents"
ON public.clinical_documents;

DROP POLICY IF EXISTS "Anyone authenticated can read document_chunks"
ON public.document_chunks;
DROP POLICY IF EXISTS "Allow public read access to clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow read access to public clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow read access to own private clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow doctors to read patient clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow owners to insert their clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow owners to update their clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow owners to delete their clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow backend write access to clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can read clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can insert clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can delete clinical_documents" ON public.clinical_documents;

DROP POLICY IF EXISTS "Allow public read access to document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Allow read access to document_chunks based on clinical_documents" ON public.document_chunks;
DROP POLICY IF EXISTS "Allow backend write access to document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can read document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can insert document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can delete document_chunks" ON public.document_chunks;

-- 3. Recreate strict RLS for clinical_documents
-- Public reference docs (is_private = false) can be read by anyone authenticated or anon
CREATE POLICY "Allow read access to public clinical_documents"
ON public.clinical_documents
FOR SELECT
TO anon, authenticated, service_role
USING (
    is_private = false
);

-- Private docs can be read by their owner
CREATE POLICY "Allow read access to own private clinical_documents"
ON public.clinical_documents
FOR SELECT
TO authenticated
USING (
    owner_id = auth.uid()
);

-- Allow owners to insert their own documents
CREATE POLICY "Allow owners to insert their clinical_documents"
ON public.clinical_documents
FOR INSERT
TO authenticated
WITH CHECK (
    owner_id = auth.uid()
);

-- Allow owners to update their own documents
CREATE POLICY "Allow owners to update their clinical_documents"
ON public.clinical_documents
FOR UPDATE
TO authenticated
USING (
    owner_id = auth.uid()
)
WITH CHECK (
    owner_id = auth.uid()
);

-- Only owners can delete their own documents
CREATE POLICY "Allow owners to delete their clinical_documents"
ON public.clinical_documents
FOR DELETE
TO authenticated
USING (
    owner_id = auth.uid()
);

-- Service role retains full administrative access
CREATE POLICY "Allow backend write access to clinical_documents"
ON public.clinical_documents
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 4. Recreate strict RLS for document_chunks
-- Chunks inherit the accessibility of their parent document
CREATE POLICY "Allow read access to document_chunks based on clinical_documents"
ON public.document_chunks
FOR SELECT
TO anon, authenticated, service_role
USING (
    EXISTS (
        SELECT 1 FROM public.clinical_documents cd
        WHERE cd.id = document_chunks.document_id
          AND (cd.is_private = false OR cd.owner_id = auth.uid())
    )
);

-- Service role retains full administrative access
CREATE POLICY "Allow backend write access to document_chunks"
ON public.document_chunks
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 5. Update match_document_chunks to use SECURITY INVOKER
-- We use CREATE OR REPLACE to avoid dropping the function and losing existing GRANTS
-- or breaking ongoing transactions.
CREATE OR REPLACE FUNCTION public.match_document_chunks(
    query_embedding vector(384),
    match_threshold float DEFAULT 0.0,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    metadata JSONB,
    similarity float
)
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public, pg_temp
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.content,
        dc.metadata,
        (1 - (dc.embedding <=> query_embedding))::float AS similarity
    FROM public.document_chunks dc
    WHERE (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Regrant execute permissions after drop/replace
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector, float, int) TO anon, authenticated, service_role;

-- 6. Storage Bucket Configuration
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'careflow_documents', 
    'careflow_documents', 
    false, 
    10485760, -- 10MB
    ARRAY['application/pdf', 'text/plain', 'text/markdown', 'image/jpeg', 'image/png']::text[]
) ON CONFLICT (id) DO UPDATE SET
    public = false,
    file_size_limit = 10485760,
    allowed_mime_types = ARRAY['application/pdf', 'text/plain', 'text/markdown', 'image/jpeg', 'image/png']::text[];

-- 7. Storage RLS Policies
DROP POLICY IF EXISTS "Users can upload their own documents" ON storage.objects;
DROP POLICY IF EXISTS "Users can read their own documents" ON storage.objects;
DROP POLICY IF EXISTS "Doctors can read patient documents" ON storage.objects;
DROP POLICY IF EXISTS "Users can delete their own documents" ON storage.objects;
DROP POLICY IF EXISTS "Service role has full access to documents bucket" ON storage.objects;

-- Allow users to upload to their own folder (folder name = user ID)
CREATE POLICY "Users can upload their own documents" 
ON storage.objects FOR INSERT TO authenticated 
WITH CHECK (
    bucket_id = 'careflow_documents' AND 
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to read their own documents
CREATE POLICY "Users can read their own documents" 
ON storage.objects FOR SELECT TO authenticated 
USING (
    bucket_id = 'careflow_documents' AND 
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow users to delete their own documents
CREATE POLICY "Users can delete their own documents" 
ON storage.objects FOR DELETE TO authenticated 
USING (
    bucket_id = 'careflow_documents' AND 
    (storage.foldername(name))[1] = auth.uid()::text
);

-- Allow service_role to manage all objects for indexing
CREATE POLICY "Service role has full access to documents bucket"
ON storage.objects FOR ALL TO service_role
USING (bucket_id = 'careflow_documents')
WITH CHECK (bucket_id = 'careflow_documents');
