"""Phase 8 - profiling pipeline tables

Adds:
  - profile_assessments
  - lead_scores
  - profiling_jobs

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "profile_assessments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "social_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("social_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unified_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("unified_users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("persona", sa.String(length=100), nullable=True),
        sa.Column("primary_interests", JSONB, nullable=True),
        sa.Column("secondary_interests", JSONB, nullable=True),
        sa.Column("sentiment_tone", sa.String(length=50), nullable=True),
        sa.Column("purchase_intent_score", sa.Integer(), nullable=True),
        sa.Column("influence_tier", sa.String(length=20), nullable=True),
        sa.Column("engagement_style", sa.String(length=50), nullable=True),
        sa.Column("psychographic_driver", sa.String(length=50), nullable=True),
        sa.Column("recommended_channel", sa.String(length=50), nullable=True),
        sa.Column("recommended_message_angle", sa.Text(), nullable=True),
        sa.Column("industry_fit", JSONB, nullable=True),
        sa.Column("confidence", sa.String(length=30), nullable=True),
        sa.Column("raw_llm_response", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_profile_assessments_social_profile_id",
        "profile_assessments",
        ["social_profile_id"],
    )
    op.create_index(
        "ix_profile_assessments_unified_user_id",
        "profile_assessments",
        ["unified_user_id"],
    )
    op.create_index("ix_profile_assessments_created_at", "profile_assessments", ["created_at"])

    op.create_table(
        "lead_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "social_profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("social_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "assessment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profile_assessments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("total_score", sa.Float(), nullable=False, server_default="0"),
        sa.Column("score_breakdown", JSONB, nullable=True),
        sa.Column("tier", sa.String(length=20), nullable=True),
        sa.Column("target_industries", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("assessment_id", name="uq_lead_scores_assessment_id"),
    )
    op.create_index("ix_lead_scores_social_profile_id", "lead_scores", ["social_profile_id"])
    op.create_index("ix_lead_scores_assessment_id", "lead_scores", ["assessment_id"])
    op.create_index("ix_lead_scores_tier", "lead_scores", ["tier"])
    op.create_index("ix_lead_scores_total_score", "lead_scores", ["total_score"])
    op.create_index("ix_lead_scores_created_at", "lead_scores", ["created_at"])

    op.create_table(
        "profiling_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("total_profiles", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filters_used", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_profiling_jobs_status", "profiling_jobs", ["status"])
    op.create_index("ix_profiling_jobs_created_at", "profiling_jobs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_profiling_jobs_created_at", "profiling_jobs")
    op.drop_index("ix_profiling_jobs_status", "profiling_jobs")
    op.drop_table("profiling_jobs")

    op.drop_index("ix_lead_scores_created_at", "lead_scores")
    op.drop_index("ix_lead_scores_total_score", "lead_scores")
    op.drop_index("ix_lead_scores_tier", "lead_scores")
    op.drop_index("ix_lead_scores_assessment_id", "lead_scores")
    op.drop_index("ix_lead_scores_social_profile_id", "lead_scores")
    op.drop_table("lead_scores")

    op.drop_index("ix_profile_assessments_created_at", "profile_assessments")
    op.drop_index("ix_profile_assessments_unified_user_id", "profile_assessments")
    op.drop_index("ix_profile_assessments_social_profile_id", "profile_assessments")
    op.drop_table("profile_assessments")
