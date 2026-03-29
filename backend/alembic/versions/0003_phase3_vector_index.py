"""Phase 3 — pgvector IVFFlat index for fast similarity search

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-28

The IVFFlat index enables sub-100ms cosine similarity queries at 500K+ profiles.
lists = 100 is the recommended setting for datasets in the 100K–1M range.
Re-run VACUUM ANALYZE after bulk inserts to keep the index fresh.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IVFFlat index on social_profiles.embedding (cosine distance)
    # Requires at least lists*30 rows to be useful; safe to create early.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_profiles_embedding_cosine
        ON social_profiles
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Same index on unified_users.merged_embedding for Phase 3+ lookups
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_unified_users_embedding_cosine
        ON unified_users
        USING ivfflat (merged_embedding vector_cosine_ops)
        WITH (lists = 100)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_unified_users_embedding_cosine")
    op.execute("DROP INDEX IF EXISTS ix_social_profiles_embedding_cosine")
