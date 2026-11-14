-- ==============================================================================
-- TesisStat AI — Initial Schema Migration for PostgreSQL / Supabase
-- Supports multi-tenancy, Row-Level Security (RLS), and durable foreign keys.
-- ==============================================================================

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Research Projects (Root Entity)
CREATE TABLE IF NOT EXISTS research_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id TEXT NOT NULL, -- Corresponds to auth.uid() in Supabase or session token
    title TEXT NOT NULL,
    degree TEXT,
    academic_year TEXT,
    methodology_confirmed BOOLEAN DEFAULT FALSE,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_projects_owner ON research_projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_research_projects_updated_at ON research_projects(updated_at DESC);

-- 2. Research Contexts
CREATE TABLE IF NOT EXISTS research_contexts (
    project_id UUID PRIMARY KEY REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Research Sources
CREATE TABLE IF NOT EXISTS research_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_sources_project_id ON research_sources(project_id);

-- 4. Research Documents (Metadata for uploaded PDFs, docs, etc.)
CREATE TABLE IF NOT EXISTS research_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    storage_path TEXT NOT NULL, -- Supabase Storage bucket path or S3 key
    file_size_bytes BIGINT NOT NULL,
    mime_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_documents_project_id ON research_documents(project_id);

-- 5. Research Datasets (Metadata & storage links for Excel/CSV)
CREATE TABLE IF NOT EXISTS research_datasets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    row_count INTEGER,
    column_count INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_datasets_project_id ON research_datasets(project_id);

-- 6. Research Preparation Plans & EDA
CREATE TABLE IF NOT EXISTS research_preparation_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_eda (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. Research Methodology & Packages
CREATE TABLE IF NOT EXISTS research_methodologies (
    project_id UUID PRIMARY KEY REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. Research Instruments
CREATE TABLE IF NOT EXISTS research_instruments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 9. Statistical Analyses & Results
CREATE TABLE IF NOT EXISTS research_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    analysis_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_analyses_project_id ON research_analyses(project_id);

-- 10. Agentic Conversation History
CREATE TABLE IF NOT EXISTS agentic_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES research_projects(id) ON DELETE CASCADE,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agentic_conversations_project_id ON agentic_conversations(project_id);

-- ==============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES FOR SUPABASE
-- Ensures that users can ONLY read and write data belonging to their projects.
-- ==============================================================================

ALTER TABLE research_projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_contexts ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_preparation_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_eda ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_methodologies ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_instruments ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE agentic_conversations ENABLE ROW LEVEL SECURITY;

-- Project Level RLS
CREATE POLICY "Users can manage their own research projects"
    ON research_projects
    FOR ALL
    USING (auth.uid()::text = owner_id)
    WITH CHECK (auth.uid()::text = owner_id);

-- Child Tables RLS (inherited from research_projects)
CREATE POLICY "Users can manage contexts in their projects"
    ON research_contexts FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_contexts.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage sources in their projects"
    ON research_sources FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_sources.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage documents in their projects"
    ON research_documents FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_documents.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage datasets in their projects"
    ON research_datasets FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_datasets.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage preparation plans in their projects"
    ON research_preparation_plans FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_preparation_plans.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage eda in their projects"
    ON research_eda FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_eda.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage methodologies in their projects"
    ON research_methodologies FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_methodologies.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage packages in their projects"
    ON research_packages FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_packages.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage instruments in their projects"
    ON research_instruments FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_instruments.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage analyses in their projects"
    ON research_analyses FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = research_analyses.project_id AND owner_id = auth.uid()::text));

CREATE POLICY "Users can manage agentic conversations in their projects"
    ON agentic_conversations FOR ALL
    USING (EXISTS (SELECT 1 FROM research_projects WHERE id = agentic_conversations.project_id AND owner_id = auth.uid()::text));
