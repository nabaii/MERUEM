"""Phase 5 — campaign_exports and notifications tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE notification_type_enum AS ENUM
            ('export_ready', 'export_failed', 'campaign_activated', 'campaign_completed', 'system');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE export_format_enum AS ENUM ('meta', 'twitter', 'csv');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE export_status_enum AS ENUM
            ('pending', 'exported', 'processing', 'ready', 'failed');
        EXCEPTION WHEN duplicate_object THEN null; END $$;
        """
    )
    op.execute("ALTER TYPE export_status_enum ADD VALUE IF NOT EXISTS 'processing'")
    op.execute("ALTER TYPE export_status_enum ADD VALUE IF NOT EXISTS 'ready'")

    # ── campaign_exports ─────────────────────────────────────────────────────
    op.create_table(
        "campaign_exports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "campaign_id",
            UUID(as_uuid=True),
            sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "format",
            ENUM("meta", "twitter", "csv", name="export_format_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("profile_count", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            ENUM(
                "pending", "processing", "ready", "failed",
                name="export_status_enum",
                create_type=False,
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("file_key", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
    )

    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "type",
            ENUM(
                "export_ready",
                "export_failed",
                "campaign_activated",
                "campaign_completed",
                "system",
                name="notification_type_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("data", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("campaign_exports")
    op.execute("DROP TYPE IF EXISTS notification_type_enum")
    op.execute("DROP TYPE IF EXISTS export_format_enum")
    op.execute("DROP TYPE IF EXISTS export_status_enum")
