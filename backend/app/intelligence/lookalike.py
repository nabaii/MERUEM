"""
Lookalike audience scoring — Phase 3.

Given a seed (list of profile IDs or a cluster ID), computes the centroid of
the seed's embeddings and then uses pgvector cosine distance to find the N
most similar profiles in the database.

Why a centroid?  Averaging unit vectors gives a vector that points toward the
densest region of the seed group in embedding space.  It is not a unit vector
itself after averaging, but pgvector normalises internally for the `<=>` (cosine)
operator, so the ranking is still correct.

Optional filters (location, follower range, platform) are applied as SQL
WHERE clauses *before* the ORDER BY embedding distance, which lets the index
kick in on a smaller candidate set.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.social_profile import SocialProfile


@dataclass
class LookalikeCandidate:
    profile_id: str
    username: str | None
    display_name: str | None
    platform: str
    follower_count: int | None
    location_inferred: str | None
    similarity_score: float   # 0–1, higher = more similar


def _compute_centroid(embeddings: list[list[float]]) -> list[float]:
    """Return the element-wise mean of a list of embedding vectors."""
    arr = np.array(embeddings, dtype=np.float32)
    return arr.mean(axis=0).tolist()


def _fetch_seed_embeddings(db: Session, profile_ids: list[str]) -> list[list[float]]:
    rows = (
        db.query(SocialProfile.embedding)
        .filter(
            SocialProfile.id.in_(profile_ids),
            SocialProfile.embedding.is_not(None),
        )
        .all()
    )
    return [r.embedding for r in rows if r.embedding is not None]


def _fetch_cluster_embeddings(db: Session, cluster_id: int) -> list[list[float]]:
    rows = (
        db.query(SocialProfile.embedding)
        .filter(
            SocialProfile.cluster_id == cluster_id,
            SocialProfile.embedding.is_not(None),
        )
        .all()
    )
    return [r.embedding for r in rows if r.embedding is not None]


def find_lookalikes(
    db: Session,
    *,
    seed_profile_ids: list[str] | None = None,
    seed_cluster_id: int | None = None,
    limit: int = 100,
    exclude_seed: bool = True,
    platform: str | None = None,
    min_followers: int | None = None,
    max_followers: int | None = None,
    location: str | None = None,
) -> list[LookalikeCandidate]:
    """
    Find the ``limit`` most similar profiles to the given seed.

    At least one of ``seed_profile_ids`` or ``seed_cluster_id`` is required.

    Returns an empty list if the seed has no usable embeddings.
    """
    if not seed_profile_ids and seed_cluster_id is None:
        raise ValueError("Provide seed_profile_ids or seed_cluster_id")

    # ── build seed centroid ───────────────────────────────────────────────────
    embeddings: list[list[float]] = []
    if seed_profile_ids:
        embeddings.extend(_fetch_seed_embeddings(db, seed_profile_ids))
    if seed_cluster_id is not None:
        embeddings.extend(_fetch_cluster_embeddings(db, seed_cluster_id))

    if not embeddings:
        return []

    centroid = _compute_centroid(embeddings)
    # Format for pgvector literal
    centroid_str = "[" + ",".join(f"{v:.6f}" for v in centroid) + "]"

    # ── build SQL with optional filters ──────────────────────────────────────
    where_clauses = ["embedding IS NOT NULL"]
    params: dict = {"centroid": centroid_str, "limit": limit}

    if exclude_seed and seed_profile_ids:
        where_clauses.append("id != ALL(:seed_ids)")
        params["seed_ids"] = seed_profile_ids

    if platform:
        where_clauses.append("platform = :platform")
        params["platform"] = platform

    if min_followers is not None:
        where_clauses.append("follower_count >= :min_followers")
        params["min_followers"] = min_followers

    if max_followers is not None:
        where_clauses.append("follower_count <= :max_followers")
        params["max_followers"] = max_followers

    if location:
        where_clauses.append("location_inferred ILIKE :location")
        params["location"] = f"%{location}%"

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        SELECT
            id::text,
            username,
            display_name,
            platform,
            follower_count,
            location_inferred,
            1 - (embedding <=> :centroid::vector) AS similarity_score
        FROM social_profiles
        WHERE {where_sql}
        ORDER BY embedding <=> :centroid::vector
        LIMIT :limit
    """)

    rows = db.execute(sql, params).fetchall()

    return [
        LookalikeCandidate(
            profile_id=row.id,
            username=row.username,
            display_name=row.display_name,
            platform=row.platform,
            follower_count=row.follower_count,
            location_inferred=row.location_inferred,
            similarity_score=round(float(row.similarity_score), 4),
        )
        for row in rows
    ]
