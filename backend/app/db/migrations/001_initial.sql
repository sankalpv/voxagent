-- ============================================================
-- AI Voice Agent Platform — Initial Schema
-- Runs automatically in docker-compose via initdb.d
-- ============================================================

-- Enable pgvector for knowledge base embeddings (Phase 3)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Tenants ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(255)  NOT NULL,
    api_key     VARCHAR(255)  NOT NULL UNIQUE,
    tier        VARCHAR(50)   NOT NULL DEFAULT 'standard',  -- economy|standard|premium
    is_active   BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

-- ─── Agent Configurations ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_configs (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id                UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name                     VARCHAR(255) NOT NULL,
    is_active                BOOLEAN NOT NULL DEFAULT TRUE,
    -- Natural language config: the full call logic lives in these fields
    system_prompt            TEXT NOT NULL,
    persona                  TEXT NOT NULL DEFAULT '',
    primary_goal             TEXT NOT NULL DEFAULT '',
    constraints              TEXT NOT NULL DEFAULT '',
    escalation_policy        TEXT NOT NULL DEFAULT '',
    -- Voice
    voice_name               VARCHAR(100) NOT NULL DEFAULT 'en-US-Journey-D',
    language_code            VARCHAR(20)  NOT NULL DEFAULT 'en-US',
    -- Tools (JSON array of tool names)
    enabled_tools            JSONB NOT NULL DEFAULT '[]',
    voicemail_script         TEXT,
    max_call_duration_seconds INTEGER NOT NULL DEFAULT 600,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Contacts ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS contacts (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number VARCHAR(50)  NOT NULL,
    first_name   VARCHAR(100),
    last_name    VARCHAR(100),
    email        VARCHAR(255),
    company      VARCHAR(255),
    metadata     JSONB NOT NULL DEFAULT '{}',
    is_dnc       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, phone_number)
);

-- ─── Calls ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS calls (
    id                       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id                UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    agent_id                 UUID REFERENCES agent_configs(id),
    contact_id               UUID REFERENCES contacts(id),
    -- Telnyx
    telnyx_call_control_id   VARCHAR(255) UNIQUE,
    telnyx_call_leg_id       VARCHAR(255),
    -- Call details
    direction                VARCHAR(20)  NOT NULL DEFAULT 'outbound',
    to_number                VARCHAR(50)  NOT NULL,
    from_number              VARCHAR(50)  NOT NULL,
    status                   VARCHAR(50)  NOT NULL DEFAULT 'pending',
    outcome                  VARCHAR(50),
    -- Timing
    started_at               TIMESTAMPTZ,
    answered_at              TIMESTAMPTZ,
    ended_at                 TIMESTAMPTZ,
    duration_seconds         INTEGER,
    -- Intelligence
    transcript               TEXT,
    ai_summary               TEXT,
    sentiment                VARCHAR(20),
    -- Cost
    cost_usd                 NUMERIC(10, 6),
    recording_url            VARCHAR(500),
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Call Events (turn-by-turn transcript) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS call_events (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    call_id      UUID NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    turn_index   INTEGER NOT NULL,
    role         VARCHAR(20) NOT NULL,   -- user | agent | system
    content      TEXT NOT NULL,
    tool_calls   JSONB,
    tool_results JSONB,
    latency_ms   INTEGER,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── DNC List ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dnc_numbers (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    phone_number VARCHAR(50) NOT NULL,
    reason       VARCHAR(255),
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, phone_number)
);

-- ─── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_agent_configs_tenant ON agent_configs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_contacts_tenant_phone ON contacts(tenant_id, phone_number);
CREATE INDEX IF NOT EXISTS idx_calls_tenant ON calls(tenant_id);
CREATE INDEX IF NOT EXISTS idx_calls_control_id ON calls(telnyx_call_control_id);
CREATE INDEX IF NOT EXISTS idx_calls_status ON calls(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_call_events_call ON call_events(call_id, turn_index);
CREATE INDEX IF NOT EXISTS idx_dnc_tenant_phone ON dnc_numbers(tenant_id, phone_number);

-- ─── Row-Level Security (multi-tenant isolation) ──────────────────────────────
-- Applications set `app.current_tenant_id` before queries.
-- All SELECT/INSERT/UPDATE/DELETE are automatically scoped to that tenant.

ALTER TABLE agent_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE contacts      ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls         ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_events   ENABLE ROW LEVEL SECURITY;
ALTER TABLE dnc_numbers   ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON agent_configs
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation ON contacts
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation ON calls
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

CREATE POLICY tenant_isolation ON call_events
    USING (call_id IN (
        SELECT id FROM calls
        WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID
    ));

CREATE POLICY tenant_isolation ON dnc_numbers
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);

-- ─── Seed: default tenant for development ────────────────────────────────────
INSERT INTO tenants (id, name, api_key, tier)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Dev Tenant',
    'dev-api-key-change-in-production',
    'standard'
) ON CONFLICT DO NOTHING;

-- ─── Knowledge Bases (RAG) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_bases (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id    UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Documents ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    filename          VARCHAR(255) NOT NULL,
    content_type      VARCHAR(100),
    status            VARCHAR(50) DEFAULT 'processing',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── Document Chunks (Vector Store) ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index   INTEGER NOT NULL,
    chunk_text    TEXT NOT NULL,
    embedding     VECTOR(768) NOT NULL
);

-- ─── Vector Index (HNSW for low latency ANN search) ──────────────────────────
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
ON document_chunks USING hnsw (embedding vector_cosine_ops);

