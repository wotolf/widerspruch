"""case_phase_history: Tabelle für Phase-Übergänge

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-14
"""
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS case_phase_history (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            from_phase TEXT NOT NULL,
            to_phase TEXT NOT NULL,
            reason TEXT NOT NULL,
            transitioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_case_phase_history_case_id "
        "ON case_phase_history(case_id)"
    )


def downgrade() -> None:
    pass
