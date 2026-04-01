"""Phase 7 — multi-source ingestion columns

Adds:
  - social_profiles.source_method (api | bot | manual)
  - Index on source_method for filtering by ingestion type

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "social_profiles",
        sa.Column(
            "source_method",
            sa.String(20),
            nullable=True,
            server_default="api",
            comment="api | bot | manual",
        ),
    )
    op.create_index(
        "ix_social_profiles_source_method",
        "social_profiles",
        ["source_method"],
    )


def downgrade() -> None:
    op.drop_index("ix_social_profiles_source_method", "social_profiles")
    op.drop_column("social_profiles", "source_method")
