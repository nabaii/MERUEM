"""Phase 10 — Ghost Virality pipeline tables

Adds:
  - ghost_scout_jobs
  - ghost_reel_snapshots
  - ghost_viral_posts
  - ghost_pattern_cards
  - ghost_trial_reels
  - ghost_niche_percentiles

Revision ID: 0009
Revises: 0008
Create Date: 2026-04-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ enums
    ghost_job_status_enum = sa.Enum(
        "pending", "running", "completed", "failed",
        name="ghost_job_status_enum",
    )
    ghost_strategy_label_enum = sa.Enum(
        "high_dm_share", "watch_time_arbitrage", "audio_driven",
        "polarizing", "utility", "unknown",
        name="ghost_strategy_label_enum",
    )
    ghost_audio_type_enum = sa.Enum(
        "trending", "original", "unknown",
        name="ghost_audio_type_enum",
    )
    ghost_trial_status_enum = sa.Enum(
        "pending", "live", "promoted", "rejected",
        name="ghost_trial_status_enum",
    )

    # --------------------------------------------------------- ghost_scout_jobs
    op.create_table(
        "ghost_scout_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("niche", sa.String(120), nullable=False),
        sa.Column("competitor_accounts", JSONB, nullable=True),
        sa.Column("status", ghost_job_status_enum, nullable=False, server_default="pending"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("reels_scraped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ghost_viral_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.String(2000), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_scout_jobs_niche", "ghost_scout_jobs", ["niche"])
    op.create_index("ix_ghost_scout_jobs_status", "ghost_scout_jobs", ["status"])
    op.create_index("ix_ghost_scout_jobs_created_at", "ghost_scout_jobs", ["created_at"])

    # ----------------------------------------------------- ghost_reel_snapshots
    op.create_table(
        "ghost_reel_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("reel_id", sa.String(255), nullable=False),
        sa.Column("account_username", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(120), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("comment_count", sa.Integer(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("thumbnail_url", sa.String(1024), nullable=True),
        sa.Column("permalink", sa.String(1024), nullable=True),
        sa.Column("audio_id", sa.String(255), nullable=True),
        sa.Column("raw_json", JSONB, nullable=True),
        sa.Column("pass_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scout_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_snapshots_reel_id", "ghost_reel_snapshots", ["reel_id"])
    op.create_index("ix_ghost_snapshots_account", "ghost_reel_snapshots", ["account_username"])
    op.create_index("ix_ghost_snapshots_niche", "ghost_reel_snapshots", ["niche"])
    op.create_index("ix_ghost_snapshots_job", "ghost_reel_snapshots", ["scout_job_id"])
    op.create_index("ix_ghost_snapshots_scraped_at", "ghost_reel_snapshots", ["scraped_at"])
    op.create_index("ix_ghost_snapshots_reel_pass", "ghost_reel_snapshots", ["reel_id", "pass_index"])

    # ------------------------------------------------------- ghost_viral_posts
    op.create_table(
        "ghost_viral_posts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("reel_id", sa.String(255), nullable=False),
        sa.Column("account_username", sa.String(255), nullable=False),
        sa.Column("niche", sa.String(120), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("comment_count", sa.Integer(), nullable=True),
        sa.Column("follower_count", sa.Integer(), nullable=True),
        sa.Column("outlier_reach_ratio", sa.Float(), nullable=True),
        sa.Column("ghost_virality_delta", sa.Float(), nullable=True),
        sa.Column("like_percentile", sa.Float(), nullable=True),
        sa.Column("view_velocity", sa.Float(), nullable=True),
        sa.Column("like_velocity", sa.Float(), nullable=True),
        sa.Column("strategy_label", ghost_strategy_label_enum, nullable=True),
        sa.Column("comment_sentiment", sa.String(20), nullable=True),
        sa.Column("permalink", sa.String(1024), nullable=True),
        sa.Column("thumbnail_url", sa.String(1024), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pattern_card_ready", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_viral_reel_id", "ghost_viral_posts", ["reel_id"], unique=True)
    op.create_index("ix_ghost_viral_account", "ghost_viral_posts", ["account_username"])
    op.create_index("ix_ghost_viral_niche", "ghost_viral_posts", ["niche"])
    op.create_index("ix_ghost_viral_detected", "ghost_viral_posts", ["detected_at"])
    op.create_index("ix_ghost_viral_pattern_ready", "ghost_viral_posts", ["pattern_card_ready"])
    op.create_index("ix_ghost_viral_niche_delta", "ghost_viral_posts", ["niche", "ghost_virality_delta"])

    # ----------------------------------------------------- ghost_pattern_cards
    op.create_table(
        "ghost_pattern_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ghost_post_id", UUID(as_uuid=True), nullable=False),
        sa.Column("hook_duration_seconds", sa.Float(), nullable=True),
        sa.Column("hook_clip_path", sa.String(1024), nullable=True),
        sa.Column("scene_cut_count", sa.Integer(), nullable=True),
        sa.Column("transcript_snippet", sa.Text(), nullable=True),
        sa.Column("transcript_language", sa.String(10), nullable=True),
        sa.Column("transcript_confidence", sa.Float(), nullable=True),
        sa.Column("visual_text", sa.Text(), nullable=True),
        sa.Column("audio_type", ghost_audio_type_enum, nullable=True),
        sa.Column("audio_id", sa.String(255), nullable=True),
        sa.Column("audio_name", sa.String(512), nullable=True),
        sa.Column("hook_archetype", sa.String(120), nullable=True),
        sa.Column("raw_card", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_pattern_post_id", "ghost_pattern_cards", ["ghost_post_id"], unique=True)

    # ------------------------------------------------------ ghost_trial_reels
    op.create_table(
        "ghost_trial_reels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ghost_post_id", UUID(as_uuid=True), nullable=True),
        sa.Column("niche", sa.String(120), nullable=True),
        sa.Column("variation_label", sa.String(255), nullable=True),
        sa.Column("post_url", sa.String(1024), nullable=True),
        sa.Column("views_at_1k", sa.Integer(), nullable=True),
        sa.Column("completion_rate", sa.Float(), nullable=True),
        sa.Column("likes", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("shares", sa.Integer(), nullable=True),
        sa.Column("status", ghost_trial_status_enum, nullable=False, server_default="pending"),
        sa.Column("green_light", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_trial_ghost_post", "ghost_trial_reels", ["ghost_post_id"])
    op.create_index("ix_ghost_trial_niche", "ghost_trial_reels", ["niche"])
    op.create_index("ix_ghost_trial_status", "ghost_trial_reels", ["status"])
    op.create_index("ix_ghost_trial_created_at", "ghost_trial_reels", ["created_at"])

    # ------------------------------------------------- ghost_niche_percentiles
    op.create_table(
        "ghost_niche_percentiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("niche", sa.String(120), nullable=False),
        sa.Column("sample_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("p10", sa.Float(), nullable=True),
        sa.Column("p30", sa.Float(), nullable=True),
        sa.Column("p50", sa.Float(), nullable=True),
        sa.Column("p70", sa.Float(), nullable=True),
        sa.Column("p90", sa.Float(), nullable=True),
        sa.Column("outlier_reach_threshold", sa.Float(), nullable=False, server_default="20"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ghost_niche_percentiles_niche", "ghost_niche_percentiles", ["niche"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ghost_niche_percentiles_niche", "ghost_niche_percentiles")
    op.drop_table("ghost_niche_percentiles")

    op.drop_index("ix_ghost_trial_created_at", "ghost_trial_reels")
    op.drop_index("ix_ghost_trial_status", "ghost_trial_reels")
    op.drop_index("ix_ghost_trial_niche", "ghost_trial_reels")
    op.drop_index("ix_ghost_trial_ghost_post", "ghost_trial_reels")
    op.drop_table("ghost_trial_reels")

    op.drop_index("ix_ghost_pattern_post_id", "ghost_pattern_cards")
    op.drop_table("ghost_pattern_cards")

    op.drop_index("ix_ghost_viral_niche_delta", "ghost_viral_posts")
    op.drop_index("ix_ghost_viral_pattern_ready", "ghost_viral_posts")
    op.drop_index("ix_ghost_viral_detected", "ghost_viral_posts")
    op.drop_index("ix_ghost_viral_niche", "ghost_viral_posts")
    op.drop_index("ix_ghost_viral_account", "ghost_viral_posts")
    op.drop_index("ix_ghost_viral_reel_id", "ghost_viral_posts")
    op.drop_table("ghost_viral_posts")

    op.drop_index("ix_ghost_snapshots_reel_pass", "ghost_reel_snapshots")
    op.drop_index("ix_ghost_snapshots_scraped_at", "ghost_reel_snapshots")
    op.drop_index("ix_ghost_snapshots_job", "ghost_reel_snapshots")
    op.drop_index("ix_ghost_snapshots_niche", "ghost_reel_snapshots")
    op.drop_index("ix_ghost_snapshots_account", "ghost_reel_snapshots")
    op.drop_index("ix_ghost_snapshots_reel_id", "ghost_reel_snapshots")
    op.drop_table("ghost_reel_snapshots")

    op.drop_index("ix_ghost_scout_jobs_created_at", "ghost_scout_jobs")
    op.drop_index("ix_ghost_scout_jobs_status", "ghost_scout_jobs")
    op.drop_index("ix_ghost_scout_jobs_niche", "ghost_scout_jobs")
    op.drop_table("ghost_scout_jobs")

    sa.Enum(name="ghost_trial_status_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ghost_audio_type_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ghost_strategy_label_enum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ghost_job_status_enum").drop(op.get_bind(), checkfirst=True)
