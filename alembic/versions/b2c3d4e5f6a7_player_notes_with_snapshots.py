"""player_notes: fact_id + snapshot_value für Journal/Vergleichen

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-12
"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE player_notes
            ADD COLUMN IF NOT EXISTS fact_id UUID NULL REFERENCES facts(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS snapshot_value TEXT NULL
    """)


def downgrade() -> None:
    pass
