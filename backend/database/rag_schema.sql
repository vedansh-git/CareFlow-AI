-- ============================================================
-- CareFlow AI - RAG Vector Store & Clinical Knowledge Schema
-- ============================================================
-- PURPOSE:
--   1. Enable pgvector extension for dense vector similarity search.
--   2. Define clinical_documents and document_chunks tables.
--   3. Create HNSW index for high-performance vector search.
--   4. Expose match_document_chunks() RPC with SECURITY DEFINER and pinned search_path.
--   5. Enforce strict Row Level Security (RLS):
--      - anon & authenticated: Read-only SELECT access and search execution.
--      - service_role: Trusted administrative read/write access for document ingestion and cleanup.
-- ============================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Clinical Documents Table (Metadata & Source tracking)
CREATE TABLE IF NOT EXISTS public.clinical_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    source TEXT,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Document Chunks Table (Embeddings & Text Segments)
CREATE TABLE IF NOT EXISTS public.document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.clinical_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    embedding vector(384), -- 384-dimensional embeddings (e.g. all-MiniLM-L6-v2)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. HNSW Index for Vector Cosine Similarity Search
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
ON public.document_chunks 
USING hnsw (embedding vector_cosine_ops);

-- 5. Similarity Search Function (Safe search_path & SECURITY DEFINER)
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
SECURITY DEFINER
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

-- ============================================================
-- 6. Table & Function Permissions (Least Privilege Principle)
-- ============================================================

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Public / Authenticated: Read-only access to clinical documents and chunks
GRANT SELECT ON TABLE public.clinical_documents TO anon, authenticated;
GRANT SELECT ON TABLE public.document_chunks TO anon, authenticated;

-- Trusted Backend (service_role): Full read/write access for document indexing
GRANT ALL ON TABLE public.clinical_documents TO service_role;
GRANT ALL ON TABLE public.document_chunks TO service_role;

-- Allow similarity search function execution
GRANT EXECUTE ON FUNCTION public.match_document_chunks(vector, float, int) TO anon, authenticated, service_role;

-- ============================================================
-- 7. Row Level Security (RLS)
-- ============================================================

ALTER TABLE public.clinical_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

-- Clean existing policies
DROP POLICY IF EXISTS "Allow public read access to clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Allow backend write access to clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can read clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can insert clinical_documents" ON public.clinical_documents;
DROP POLICY IF EXISTS "Anyone can delete clinical_documents" ON public.clinical_documents;

DROP POLICY IF EXISTS "Allow public read access to document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Allow backend write access to document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can read document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can insert document_chunks" ON public.document_chunks;
DROP POLICY IF EXISTS "Anyone can delete document_chunks" ON public.document_chunks;

-- Read policy: Anyone (anon, authenticated, service_role) can read knowledge base
CREATE POLICY "Allow public read access to clinical_documents"
ON public.clinical_documents
FOR SELECT
TO anon, authenticated, service_role
USING (true);

CREATE POLICY "Allow public read access to document_chunks"
ON public.document_chunks
FOR SELECT
TO anon, authenticated, service_role
USING (true);

-- Write policies: Only service_role can INSERT, UPDATE, DELETE
CREATE POLICY "Allow backend write access to clinical_documents"
ON public.clinical_documents
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Allow backend write access to document_chunks"
ON public.document_chunks
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);
