"""Initial schema — all Phase 1 tables + pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-03-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Enable pgvector extension
    # ------------------------------------------------------------------ #
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ #
    # Enums
    # ------------------------------------------------------------------ #
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE role_enum AS ENUM ('admin', 'client');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status_enum AS ENUM ('pending', 'running', 'completed', 'failed');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE link_status_enum AS ENUM ('pending', 'confirmed', 'rejected');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE campaign_status_enum AS ENUM ('draft', 'active', 'exported', 'completed');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE export_status_enum AS ENUM ('pending', 'exported', 'failed');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)

    # ------------------------------------------------------------------ #
    # accounts
    # ------------------------------------------------------------------ #
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255)),
        sa.Column("role", postgresql.ENUM("admin", "client", name="role_enum", create_type=False), nullable=False, server_default="client"),
        sa.Column("api_key", sa.String(64)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_accounts_email", "accounts", ["email"], unique=True)
    op.create_index("ix_accounts_api_key", "accounts", ["api_key"], unique=True)

    # ------------------------------------------------------------------ #
    # clusters (created before social_profiles due to FK)
    # ------------------------------------------------------------------ #
    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("label", sa.String(255)),
        sa.Column("description", sa.String(1000)),
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("top_interests", postgresql.JSONB()),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------ #
    # unified_users
    # ------------------------------------------------------------------ #
    op.create_table(
        "unified_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("canonical_name", sa.String(255)),
        sa.Column("canonical_email", sa.String(255)),
        sa.Column("canonical_location", sa.String(255)),
        sa.Column("merged_embedding", Vector(384)),
        sa.Column("merged_interests", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_unified_users_canonical_email", "unified_users", ["canonical_email"])

    # ------------------------------------------------------------------ #
    # social_profiles
    # ------------------------------------------------------------------ #
    op.create_table(
        "social_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("unified_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("unified_users.id")),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("platform_user_id", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("display_name", sa.String(255)),
        sa.Column("bio", sa.String(1000)),
        sa.Column("profile_image_url", sa.String(500)),
        sa.Column("location_raw", sa.String(255)),
        sa.Column("location_inferred", sa.String(255)),
        sa.Column("follower_count", sa.Integer()),
        sa.Column("following_count", sa.Integer()),
        sa.Column("tweet_count", sa.Integer()),
        sa.Column("embedding", Vector(384)),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id")),
        sa.Column("affinity_score", sa.Float()),
        sa.Column("last_collected", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_social_profiles_unified_user_id", "social_profiles", ["unified_user_id"])
    op.create_index("ix_social_profiles_cluster_id", "social_profiles", ["cluster_id"])
    op.create_index("ix_social_profiles_username", "social_profiles", ["username"])
    op.create_unique_constraint(
        "uq_social_profiles_platform_user", "social_profiles", ["platform", "platform_user_id"]
    )

    # ------------------------------------------------------------------ #
    # posts
    # ------------------------------------------------------------------ #
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_profiles.id"), nullable=False),
        sa.Column("platform_post_id", sa.String(255)),
        sa.Column("content", sa.String(4000)),
        sa.Column("post_type", sa.String(50)),
        sa.Column("likes", sa.Integer()),
        sa.Column("reposts", sa.Integer()),
        sa.Column("replies", sa.Integer()),
        sa.Column("entities", postgresql.JSONB()),
        sa.Column("sentiment_score", sa.Float()),
        sa.Column("language", sa.String(10)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_posts_profile_id", "posts", ["profile_id"])
    op.create_index("ix_posts_platform_post_id", "posts", ["platform_post_id"])
    op.create_index("ix_posts_posted_at", "posts", ["posted_at"])

    # ------------------------------------------------------------------ #
    # profile_interests
    # ------------------------------------------------------------------ #
    op.create_table(
        "profile_interests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_profiles.id"), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
    )
    op.create_index("ix_profile_interests_profile_id", "profile_interests", ["profile_id"])
    op.create_index("ix_profile_interests_topic", "profile_interests", ["topic"])

    # ------------------------------------------------------------------ #
    # profile_links
    # ------------------------------------------------------------------ #
    op.create_table(
        "profile_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("unified_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("unified_users.id")),
        sa.Column("source_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_profiles.id"), nullable=False),
        sa.Column("target_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("social_profiles.id"), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("match_method", sa.String(100), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "confirmed", "rejected", name="link_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_profile_links_unified_user_id", "profile_links", ["unified_user_id"])

    # ------------------------------------------------------------------ #
    # cluster_metrics
    # ------------------------------------------------------------------ #
    op.create_table(
        "cluster_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("avg_engagement", sa.Float()),
        sa.Column("avg_followers", sa.Float()),
        sa.Column("interest_distribution", postgresql.JSONB()),
        sa.Column("computed_date", sa.Date(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_cluster_metrics_cluster_id", "cluster_metrics", ["cluster_id"])
    op.create_index("ix_cluster_metrics_computed_date", "cluster_metrics", ["computed_date"])

    # ------------------------------------------------------------------ #
    # campaigns
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id")),
        sa.Column("status", postgresql.ENUM("draft", "active", "exported", "completed", name="campaign_status_enum", create_type=False), nullable=False, server_default="draft"),
        sa.Column("filters", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_campaigns_owner_id", "campaigns", ["owner_id"])

    # ------------------------------------------------------------------ #
    # campaign_audiences
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaign_audiences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id"), nullable=False),
        sa.Column("cluster_id", sa.Integer(), sa.ForeignKey("clusters.id")),
        sa.Column("estimated_reach", sa.Integer()),
        sa.Column("export_status", postgresql.ENUM("pending", "exported", "failed", name="export_status_enum", create_type=False), nullable=False, server_default="pending"),
    )
    op.create_index("ix_campaign_audiences_campaign_id", "campaign_audiences", ["campaign_id"])
    op.create_index("ix_campaign_audiences_cluster_id", "campaign_audiences", ["cluster_id"])

    # ------------------------------------------------------------------ #
    # collection_jobs
    # ------------------------------------------------------------------ #
    op.create_table(
        "collection_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("status", postgresql.ENUM("pending", "running", "completed", "failed", name="job_status_enum", create_type=False), nullable=False, server_default="pending"),
        sa.Column("params", postgresql.JSONB()),
        sa.Column("celery_task_id", sa.String(255)),
        sa.Column("profiles_collected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2000)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_collection_jobs_created_at", "collection_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("collection_jobs")
    op.drop_table("campaign_audiences")
    op.drop_table("campaigns")
    op.drop_table("cluster_metrics")
    op.drop_table("profile_links")
    op.drop_table("profile_interests")
    op.drop_table("posts")
    op.drop_table("social_profiles")
    op.drop_table("unified_users")
    op.drop_table("clusters")
    op.drop_table("accounts")

    op.execute("DROP TYPE IF EXISTS export_status_enum")
    op.execute("DROP TYPE IF EXISTS campaign_status_enum")
    op.execute("DROP TYPE IF EXISTS link_status_enum")
    op.execute("DROP TYPE IF EXISTS job_status_enum")
    op.execute("DROP TYPE IF EXISTS role_enum")
    op.execute("DROP EXTENSION IF EXISTS vector")
