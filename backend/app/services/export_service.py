from __future__ import annotations

import csv
import io
from collections.abc import Sequence

from app.db.models.profiling import LeadScore, ProfileAssessment
from app.db.models.social_profile import SocialProfile
from app.export.csv_generator import save_export_file


def _join_values(values: list[str] | None) -> str:
    return "; ".join(values or [])


def _split_name(display_name: str | None, username: str | None) -> tuple[str, str]:
    source = (display_name or username or "").strip()
    if not source:
        return "", ""
    parts = source.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


class ExportService:
    def build_generic_csv(
        self,
        rows: Sequence[tuple[LeadScore, ProfileAssessment, SocialProfile]],
    ) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "handle",
                "platform",
                "display_name",
                "persona",
                "primary_interests",
                "sentiment_tone",
                "purchase_intent_score",
                "influence_tier",
                "engagement_style",
                "psychographic_driver",
                "recommended_channel",
                "recommended_message_angle",
                "industry_fit",
                "lead_score",
                "lead_tier",
                "confidence",
            ]
        )
        for lead_score, assessment, profile in rows:
            writer.writerow(
                [
                    profile.username or "",
                    profile.platform,
                    profile.display_name or "",
                    assessment.persona or "",
                    _join_values(assessment.primary_interests),
                    assessment.sentiment_tone or "",
                    assessment.purchase_intent_score or "",
                    assessment.influence_tier or "",
                    assessment.engagement_style or "",
                    assessment.psychographic_driver or "",
                    assessment.recommended_channel or "",
                    assessment.recommended_message_angle or "",
                    _join_values(assessment.industry_fit),
                    round(lead_score.total_score, 4),
                    lead_score.tier or "",
                    assessment.confidence or "",
                ]
            )
        return buf.getvalue().encode("utf-8")

    def build_hubspot_csv(
        self,
        rows: Sequence[tuple[LeadScore, ProfileAssessment, SocialProfile]],
    ) -> bytes:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "social_handle",
                "social_platform",
                "firstname",
                "lastname",
                "meruem_persona",
                "meruem_interests",
                "meruem_intent_score",
                "lead_score",
                "meruem_lead_tier",
                "meruem_best_channel",
                "meruem_pitch_angle",
                "meruem_industry_fit",
            ]
        )
        for lead_score, assessment, profile in rows:
            first_name, last_name = _split_name(profile.display_name, profile.username)
            writer.writerow(
                [
                    profile.username or "",
                    profile.platform,
                    first_name,
                    last_name,
                    assessment.persona or "",
                    _join_values(assessment.primary_interests),
                    assessment.purchase_intent_score or "",
                    round(lead_score.total_score, 4),
                    lead_score.tier or "",
                    assessment.recommended_channel or "",
                    assessment.recommended_message_angle or "",
                    _join_values(assessment.industry_fit),
                ]
            )
        return buf.getvalue().encode("utf-8")

    def save_export(self, data: bytes, file_key: str) -> str:
        return save_export_file(data, file_key)
