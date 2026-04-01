PROFILING_SYSTEM_PROMPT = """
You are a Nigerian market audience intelligence analyst working for a
marketing platform. Your job is to analyze public social media profiles
and produce structured psychographic assessments.

You understand Nigerian digital culture: Pidgin English, code-switching
between English and Yoruba/Igbo/Hausa, local slang, and the distinct
consumer behavior patterns of the Nigerian market.

Always return your assessment in the exact structured format requested.
Never add commentary outside the format.
""".strip()


PROFILING_USER_TEMPLATE = """
Analyze this public social media profile:

Platform: {platform}
Handle: {handle}
Display Name: {display_name}
Bio: {bio}
Followers: {follower_count}
Following: {following_count}
Location (stated): {location_stated}
Location (inferred): {location_inferred}

Recent posts:
{recent_posts_formatted}

Detected entities: {entities}
Existing sentiment score (avg): {avg_sentiment}
Cluster membership: {cluster_label}
Notable hashtags: {hashtags}

Return your analysis in this exact JSON format:
{{
  "persona": "Trendy Student | Hustling Professional |
              Entrepreneurial Explorer | Family-Oriented Consumer |
              Other: [specify]",
  "primary_interests": ["interest1", "interest2", "... max 5"],
  "secondary_interests": ["interest1", "... max 3"],
  "sentiment_tone": "Optimistic | Neutral | Frustrated |
                     Aspirational | Cynical",
  "purchase_intent_score": 1-10,
  "influence_tier": "Nano | Micro | Mid | Macro",
  "engagement_style": "Lurker | Reactor | Commenter |
                      Creator | Amplifier",
  "psychographic_driver": "Status | Security | Community |
                          Achievement | Freedom",
  "recommended_channel": "WhatsApp | Instagram DM |
                         Twitter DM | Email | LinkedIn",
  "recommended_message_angle": "one sentence",
  "industry_fit": ["industry1", "industry2"],
  "confidence": "Low | Medium | High"
}}
""".strip()


STRICT_JSON_SUFFIX = "Respond ONLY with valid JSON. Do not include markdown fences."
