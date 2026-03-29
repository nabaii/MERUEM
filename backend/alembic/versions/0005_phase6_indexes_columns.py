"""Phase 6 — performance indexes, verified + engagement_rate columns

Adds:
  - social_profiles.verified (boolean)
  - social_profiles.engagement_rate (float)
  - Composite performance indexes for common query patterns

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── New columns on social_profiles ───────────────────────────────────────
    op.add_column(
        "social_profiles",
        sa.Column("verified", sa.Boolean(), nullable=True, server_default="false"),
    )
    op.add_column(
        "social_profiles",
        sa.Column("engagement_rate", sa.Float(), nullable=True),
    )

    # ── Performance indexes ───────────────────────────────────────────────────

    # Composite: platform filter + follower sort (audience explorer)
    op.create_index(
        "ix_social_profiles_platform_follower_count",
        "social_profiles",
        ["platform", "follower_count"],
    )

    # Composite: cluster + follower (cluster profile listing)
    op.create_index(
        "ix_social_profiles_cluster_follower_count",
        "social_profiles",
        ["cluster_id", "follower_count"],
    )

    # Location text search support
    op.create_index(
        "ix_social_profiles_location_inferred",
        "social_profiles",
        ["location_inferred"],
    )

    # Composite: unprocessed posts per profile (processing queue)
    op.create_index(
        "ix_posts_is_processed_profile_id",
        "posts",
        ["is_processed", "profile_id"],
    )

    # Notifications: unread per account (notification bell query)
    op.create_index(
        "ix_notifications_account_is_read",
        "notifications",
        ["account_id", "is_read"],
    )

    # Campaign exports: campaign + status (export polling)
    op.create_index(
        "ix_campaign_exports_campaign_status",
        "campaign_exports",
        ["campaign_id", "status"],
    )

    # Partial index for embedding queue (profiles missing embeddings)
    op.execute(
        "CREATE INDEX ix_social_profiles_no_embedding "
        "ON social_profiles (id) "
        "WHERE embedding IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_social_profiles_no_embedding")
    op.drop_index("ix_campaign_exports_campaign_status", "campaign_exports")
    op.drop_index("ix_notifications_account_is_read", "notifications")
    op.drop_index("ix_posts_is_processed_profile_id", "posts")
    op.drop_index("ix_social_profiles_location_inferred", "social_profiles")
    op.drop_index("ix_social_profiles_cluster_follower_count", "social_profiles")
    op.drop_index("ix_social_profiles_platform_follower_count", "social_profiles")
    op.drop_column("social_profiles", "engagement_rate")
    op.drop_column("social_profiles", "verified")
