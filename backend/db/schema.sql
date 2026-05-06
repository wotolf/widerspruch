-- Widerspruch — Initial Schema
-- Run via: psql $DATABASE_URL -f backend/db/schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Players & Profile
-- ============================================================

CREATE TABLE IF NOT EXISTS players (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    discord_id TEXT UNIQUE NOT NULL,
    onboarded_at TIMESTAMPTZ,
    reality_score FLOAT NOT NULL DEFAULT 1.0 CHECK (reality_score >= 0 AND reality_score <= 1),
    settings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_profiles (
    player_id UUID PRIMARY KEY REFERENCES players(id) ON DELETE CASCADE,
    city TEXT,
    neighborhood TEXT,
    routine TEXT,
    close_people JSONB DEFAULT '[]'::jsonb,
    fears JSONB DEFAULT '[]'::jsonb,
    locations JSONB DEFAULT '[]'::jsonb,
    raw_answers JSONB DEFAULT '{}'::jsonb,
    personalization_intensity TEXT NOT NULL DEFAULT 'medium'
        CHECK (personalization_intensity IN ('low', 'medium', 'high'))
);

-- ============================================================
-- Cases
-- ============================================================

CREATE TABLE IF NOT EXISTS cases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    phase TEXT NOT NULL DEFAULT 'opening'
        CHECK (phase IN ('opening', 'investigation', 'first_reveal', 'second_reveal', 'finale', 'closed'))
);

CREATE INDEX idx_cases_player_id ON cases(player_id);

-- ============================================================
-- Truth Engine: Facts & Layers
-- ============================================================

CREATE TABLE IF NOT EXISTS facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_facts_case_id ON facts(case_id);

CREATE TABLE IF NOT EXISTS fact_layers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fact_id UUID NOT NULL REFERENCES facts(id) ON DELETE CASCADE,
    layer_type TEXT NOT NULL
        CHECK (layer_type IN ('truth', 'perceived', 'claimed', 'evidence')),
    value TEXT NOT NULL,
    version INT NOT NULL DEFAULT 1,
    modified_by TEXT NOT NULL DEFAULT 'system',
    modified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(fact_id, layer_type, version)
);

CREATE INDEX idx_fact_layers_fact_id ON fact_layers(fact_id);
CREATE INDEX idx_fact_layers_layer_type ON fact_layers(layer_type);

-- ============================================================
-- NPCs & Memory
-- ============================================================

CREATE TABLE IF NOT EXISTS npcs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    personality JSONB NOT NULL DEFAULT '{}'::jsonb,
    knowledge JSONB NOT NULL DEFAULT '{}'::jsonb,
    relationship_to_missing TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_npcs_case_id ON npcs(case_id);

CREATE TABLE IF NOT EXISTS npc_memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    npc_id UUID NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
    memory_text TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_npc_memories_npc_id ON npc_memories(npc_id);

-- ============================================================
-- Player Notes & Sessions
-- ============================================================

CREATE TABLE IF NOT EXISTS player_notes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_player_notes_case_id ON player_notes(case_id);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ,
    actions_taken JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE INDEX idx_sessions_case_id ON sessions(case_id);

-- ============================================================
-- Real-Time Threats (Phase 3)
-- ============================================================

CREATE TABLE IF NOT EXISTS scheduled_threats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    threat_type TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    delivered_at TIMESTAMPTZ,
    cancelled BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_scheduled_threats_scheduled_for ON scheduled_threats(scheduled_for) WHERE delivered_at IS NULL AND cancelled = FALSE;

-- ============================================================
-- Parallel Timelines (Phase 4)
-- ============================================================

CREATE TABLE IF NOT EXISTS timeline_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    timeline TEXT NOT NULL
        CHECK (timeline IN ('investigator', 'shadow', 'unknown')),
    occurred_at TIMESTAMPTZ NOT NULL,
    description TEXT NOT NULL,
    visible_to_player BOOLEAN NOT NULL DEFAULT FALSE,
    revealed_at TIMESTAMPTZ
);

CREATE INDEX idx_timeline_events_case_id ON timeline_events(case_id);
