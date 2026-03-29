"""
CSV/export generators for Meta Custom Audiences, Twitter Tailored Audiences,
and generic CSV download.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models.social_profile import SocialProfile


def _sha256(value: str) -> str:
    """Lowercase-strip then SHA-256 hex digest (Meta/Twitter PII normalisation)."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()


def generate_meta_csv(profiles: list["SocialProfile"]) -> bytes:
    """
    Meta Custom Audience upload format.
    Columns: sha256_email, name, country
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["sha256_email", "name", "country"])
    for p in profiles:
        email_hash = _sha256((p.username or "") + "@placeholder.invalid")
        location = p.location_inferred or p.location_raw or "NG"
        writer.writerow([email_hash, p.display_name or "", location])
    return buf.getvalue().encode("utf-8")


def generate_twitter_csv(profiles: list["SocialProfile"]) -> bytes:
    """
    Twitter/X Tailored Audience upload format.
    Columns: twitter_id, username
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["twitter_id", "username"])
    for p in profiles:
        writer.writerow([p.platform_user_id or "", p.username or ""])
    return buf.getvalue().encode("utf-8")


def generate_generic_csv(profiles: list["SocialProfile"]) -> bytes:
    """
    Generic CSV with all non-sensitive profile fields.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "platform", "username", "display_name",
        "follower_count", "following_count",
        "location", "bio",
        "verified", "engagement_rate",
    ])
    for p in profiles:
        writer.writerow([
            str(p.id),
            p.platform,
            p.username or "",
            p.display_name or "",
            p.follower_count or 0,
            p.following_count or 0,
            p.location_inferred or p.location_raw or "",
            (p.bio or "").replace("\n", " "),
            p.verified or False,
            round(p.engagement_rate or 0, 4),
        ])
    return buf.getvalue().encode("utf-8")


def save_export_file(data: bytes, file_key: str, base_dir: str = "raw_data") -> str:
    """
    Persist export bytes to local disk (or swap for S3 put_object).
    Returns the file_key on success.
    """
    exports_dir = os.path.join(base_dir, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    path = os.path.join(exports_dir, file_key)
    with open(path, "wb") as fh:
        fh.write(data)
    return file_key


def read_export_file(file_key: str, base_dir: str = "raw_data") -> bytes:
    """Read a previously saved export file."""
    path = os.path.join(base_dir, "exports", file_key)
    with open(path, "rb") as fh:
        return fh.read()
