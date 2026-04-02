"""Phase 9 - discovery_jobs table for Twitter/X user discovery

Adds:
  - discovery_jobs (tracks keyword-based user discovery runs)

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the discovery_status_enum type
    discovery_status_enum = sa.Enum(
        "pending", "expanding", "searching", "completed", "failed",
        name="discovery_status_enum",
    )

    op.create_table(
        "discovery_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(length=50), nullable=False, server_default="twitter"),
        sa.Column("seed_keywords", JSONB, nullable=False),
        sa.Column("expanded_keywords", JSONB, nullable=True),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            discovery_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tweets_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("location_matched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("results_data", JSONB, nullable=True),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_discovery_jobs_created_at", "discovery_jobs", ["created_at"])
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"])
    op.create_index("ix_discovery_jobs_platform", "discovery_jobs", ["platform"])


def downgrade() -> None:
    op.drop_index("ix_discovery_jobs_platform", "discovery_jobs")
    op.drop_index("ix_discovery_jobs_status", "discovery_jobs")
    op.drop_index("ix_discovery_jobs_created_at", "discovery_jobs")
    op.drop_table("discovery_jobs")

    # Drop the enum type
    sa.Enum(name="discovery_status_enum").drop(op.get_bind(), checkfirst=True)
