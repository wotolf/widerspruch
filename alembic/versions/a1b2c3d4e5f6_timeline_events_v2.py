"""Full initial schema + timeline_events v2

Creates all tables from scratch on a fresh DB (IF NOT EXISTS everywhere),
then ensures timeline_events has all new columns.

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-05-10
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # players
    op.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            discord_id TEXT UNIQUE NOT NULL,
            onboarded_at TIMESTAMPTZ,
            reality_score FLOAT NOT NULL DEFAULT 1.0
                CHECK (reality_score >= 0 AND reality_score <= 1),
            settings JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # player_profiles
    op.execute("""
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
        )
    """)

    # cases
    op.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            phase TEXT NOT NULL DEFAULT 'opening'
                CHECK (phase IN ('opening', 'investigation', 'first_reveal', 'second_reveal', 'finale', 'closed'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_player_id ON cases(player_id)")

    # facts
    op.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_facts_case_id ON facts(case_id)")

    # fact_layers
    op.execute("""
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
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_fact_layers_fact_id ON fact_layers(fact_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_fact_layers_layer_type ON fact_layers(layer_type)")

    # npcs
    op.execute("""
        CREATE TABLE IF NOT EXISTS npcs (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            personality JSONB NOT NULL DEFAULT '{}'::jsonb,
            knowledge JSONB NOT NULL DEFAULT '{}'::jsonb,
            relationship_to_missing TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_npcs_case_id ON npcs(case_id)")

    # npc_memories
    op.execute("""
        CREATE TABLE IF NOT EXISTS npc_memories (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            npc_id UUID NOT NULL REFERENCES npcs(id) ON DELETE CASCADE,
            memory_text TEXT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_npc_memories_npc_id ON npc_memories(npc_id)")

    # player_notes
    op.execute("""
        CREATE TABLE IF NOT EXISTS player_notes (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_player_notes_case_id ON player_notes(case_id)")

    # sessions
    op.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ended_at TIMESTAMPTZ,
            actions_taken JSONB NOT NULL DEFAULT '[]'::jsonb
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sessions_case_id ON sessions(case_id)")

    # scheduled_threats
    op.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_threats (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            player_id UUID NOT NULL REFERENCES players(id) ON DELETE CASCADE,
            scheduled_for TIMESTAMPTZ NOT NULL,
            threat_type TEXT NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            delivered_at TIMESTAMPTZ,
            cancelled BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_scheduled_threats_scheduled_for
        ON scheduled_threats(scheduled_for)
        WHERE delivered_at IS NULL AND cancelled = FALSE
    """)

    # timeline_events (full schema incl. new columns)
    op.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            timeline TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            description TEXT NOT NULL,
            visible_to_player BOOLEAN NOT NULL DEFAULT FALSE,
            support_score FLOAT NOT NULL DEFAULT 0.5,
            evidence_links JSONB NOT NULL DEFAULT '[]'::jsonb,
            wall_clock_slot TEXT NOT NULL DEFAULT '',
            seeded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            revealed_at TIMESTAMPTZ,
            reveal_trigger TEXT
        )
    """)
    # Ensure new columns exist when table was created by an older schema
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS support_score FLOAT NOT NULL DEFAULT 0.5")
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS evidence_links JSONB NOT NULL DEFAULT '[]'")
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS wall_clock_slot TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS seeded_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS revealed_at TIMESTAMPTZ")
    op.execute("ALTER TABLE timeline_events ADD COLUMN IF NOT EXISTS reveal_trigger TEXT")
    op.execute("ALTER TABLE timeline_events DROP CONSTRAINT IF EXISTS timeline_events_timeline_check")
    op.execute("""
        ALTER TABLE timeline_events
        ADD CONSTRAINT timeline_events_timeline_check
        CHECK (timeline IN ('investigator', 'shadow_a', 'shadow_b'))
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_timeline_events_case_id ON timeline_events(case_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_timeline_events_timeline ON timeline_events(case_id, timeline)")


def downgrade() -> None:
    pass
