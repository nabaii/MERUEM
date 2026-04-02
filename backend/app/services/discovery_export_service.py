from __future__ import annotations

import csv
import io


def _join_list(values: list[str] | None) -> str:
    return " | ".join(values or [])


class DiscoveryExportService:
    def build_csv(
        self,
        *,
        users: list[dict],
        selected_micro_influencers: list[str] | None = None,
    ) -> bytes:
        selected_set = {str(item).strip().lower() for item in selected_micro_influencers or [] if item}
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "username",
                "display_name",
                "platform_user_id",
                "user_type",
                "location_raw",
                "follower_count",
                "following_count",
                "tweet_count",
                "date_joined_twitter",
                "high_value_score",
                "high_value_band",
                "engagement_frequency_score",
                "topic_relevance_score",
                "conversation_influence_score",
                "conversion_likelihood_score",
                "hybrid_signals",
                "actionable_insights",
                "recommended_angle",
                "public_emails",
                "public_phone_numbers",
                "public_social_handles",
                "public_urls",
                "manual_followers_list",
                "manual_following_list",
                "manual_notes",
                "selected_as_micro_influencer",
            ]
        )

        for user in users:
            username = str(user.get("username") or "").strip()
            contact = user.get("public_contact_info") or {}
            writer.writerow(
                [
                    username,
                    user.get("display_name") or "",
                    user.get("platform_user_id") or "",
                    user.get("user_type") or "",
                    user.get("location_raw") or "",
                    user.get("follower_count") or 0,
                    user.get("following_count") or 0,
                    user.get("tweet_count") or 0,
                    user.get("date_joined_twitter") or "",
                    user.get("high_value_score") or 0,
                    user.get("high_value_band") or "",
                    user.get("engagement_frequency_score") or 0,
                    user.get("topic_relevance_score") or 0,
                    user.get("conversation_influence_score") or 0,
                    user.get("conversion_likelihood_score") or 0,
                    _join_list(user.get("hybrid_signals")),
                    _join_list(user.get("actionable_insights")),
                    user.get("recommended_angle") or "",
                    _join_list(contact.get("emails")),
                    _join_list(contact.get("phone_numbers")),
                    _join_list(contact.get("social_handles")),
                    _join_list(contact.get("urls")),
                    _join_list(user.get("manual_followers_list")),
                    _join_list(user.get("manual_following_list")),
                    user.get("manual_notes") or "",
                    str(username.lower() in selected_set).lower(),
                ]
            )

        return buf.getvalue().encode("utf-8")
