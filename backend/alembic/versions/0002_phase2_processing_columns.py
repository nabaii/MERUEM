"""Phase 2 — add processing tracking columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Track whether a post has been through the NLP pipeline
    op.add_column(
        "posts",
        sa.Column("is_processed", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_posts_is_processed", "posts", ["is_processed"])

    # Track when a profile's embedding was last recomputed
    op.add_column(
        "social_profiles",
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("social_profiles", "embedding_updated_at")
    op.drop_index("ix_posts_is_processed", "posts")
    op.drop_column("posts", "is_processed")
