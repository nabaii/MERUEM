"""
Phase 3 — Celery intelligence tasks.

Task graph (nightly pipeline):
  run_nightly_intelligence_pipeline
    ├── classify_profiles_task        (populate profile_interests)
    ├── cluster_profiles_task         (populate clusters + assign cluster_id)
    └── resolve_identities_task       (populate profile_links + unified_users)

Each task is idempotent: re-running replaces previous results for the same
scope rather than appending duplicates.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import date, datetime, timezone

from celery import shared_task
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.intelligence.clustering import ClusteringResult, derive_cluster_label, run_clustering
from app.intelligence.identity_resolution import REVIEW_THRESHOLD, score_pair
from app.intelligence.topic_classifier import classify_profile

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Topic classification
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.intelligence.classify_profiles_task", bind=True, acks_late=True)
def classify_profiles_task(self, profile_ids: list[str] | None = None) -> dict:
    """
    Classify profiles by topic and upsert into profile_interests.

    Args:
        profile_ids: If None, process all profiles that have posts but
                     no interests yet (initial run / catch-up).
    """
    from app.db.models.post import Post
    from app.db.models.profile_interest import ProfileInterest
    from app.db.models.social_profile import SocialProfile

    processed = 0
    db: Session = SessionLocal()
    try:
        query = db.query(SocialProfile).filter(SocialProfile.embedding.is_not(None))
        if profile_ids:
            query = query.filter(SocialProfile.id.in_(profile_ids))

        profiles = query.all()

        for profile in profiles:
            posts = (
                db.query(Post)
                .filter(Post.profile_id == profile.id)
                .order_by(Post.posted_at.desc())
                .limit(200)
                .all()
            )

            post_texts = [p.content or "" for p in posts]
            post_hashtags: list[list[str]] = []
            for p in posts:
                entities = p.entities or {}
                post_hashtags.append(entities.get("hashtags", []))

            results = classify_profile(
                bio=profile.bio,
                post_texts=post_texts,
                post_hashtags=post_hashtags,
            )

            # Delete existing interests for this profile and replace
            db.query(ProfileInterest).filter(
                ProfileInterest.profile_id == profile.id
            ).delete()

            for item in results:
                db.add(
                    ProfileInterest(
                        id=uuid.uuid4(),
                        profile_id=profile.id,
                        topic=item["topic"],
                        confidence=item["confidence"],
                    )
                )

            processed += 1

        db.commit()
        log.info("classify_profiles_task: classified %d profiles", processed)
        return {"profiles_classified": processed}

    except Exception as exc:
        db.rollback()
        log.exception("classify_profiles_task failed")
        raise self.retry(exc=exc, countdown=60, max_retries=3) from exc
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Audience clustering
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.intelligence.cluster_profiles_task", bind=True, acks_late=True)
def cluster_profiles_task(
    self,
    min_cluster_size: int = 10,
    min_samples: int = 5,
) -> dict:
    """
    Run HDBSCAN on all embedded profiles and update cluster assignments.

    This task:
      1. Fetches all profiles with embeddings.
      2. Runs HDBSCAN.
      3. Drops old cluster rows; creates new ones from the result.
      4. Updates social_profiles.cluster_id.
      5. Writes ClusterMetric snapshots.
    """
    from app.db.models.cluster import Cluster
    from app.db.models.cluster_metric import ClusterMetric
    from app.db.models.profile_interest import ProfileInterest
    from app.db.models.social_profile import SocialProfile

    db: Session = SessionLocal()
    try:
        rows = (
            db.query(SocialProfile.id, SocialProfile.embedding)
            .filter(SocialProfile.embedding.is_not(None))
            .all()
        )

        if not rows:
            log.warning("cluster_profiles_task: no embedded profiles found")
            return {"n_clusters": 0, "n_noise": 0}

        profile_ids = [str(r.id) for r in rows]
        embeddings = [r.embedding for r in rows]

        result: ClusteringResult = run_clustering(
            profile_ids=profile_ids,
            embeddings=embeddings,
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
        )

        # ── reset all existing cluster assignments ────────────────────────────
        db.query(SocialProfile).update({SocialProfile.cluster_id: None})

        # ── drop old cluster_metrics then clusters ────────────────────────────
        db.query(ClusterMetric).delete()
        db.query(Cluster).delete()
        db.flush()

        today = date.today()

        for hdb_label, member_ids in result.clusters.items():
            # Derive top interests from members
            interest_counts: Counter = Counter()
            for pid in member_ids:
                interests = (
                    db.query(ProfileInterest)
                    .filter(ProfileInterest.profile_id == pid)
                    .order_by(ProfileInterest.confidence.desc())
                    .limit(3)
                    .all()
                )
                for i in interests:
                    interest_counts[i.topic] += 1

            top_interests = [t for t, _ in interest_counts.most_common(5)]
            label = derive_cluster_label(top_interests)

            # avg follower count
            from app.db.models.social_profile import SocialProfile as SP
            import sqlalchemy.func as sqlfunc
            avg_followers = (
                db.query(sqlfunc.avg(SP.follower_count))
                .filter(SP.id.in_(member_ids))
                .scalar()
            )

            cluster = Cluster(
                label=label,
                member_count=len(member_ids),
                top_interests={t: int(c) for t, c in interest_counts.most_common(10)},
                last_updated=datetime.now(timezone.utc),
            )
            db.add(cluster)
            db.flush()  # get cluster.id

            # assign profiles
            db.query(SocialProfile).filter(
                SocialProfile.id.in_(member_ids)
            ).update({SocialProfile.cluster_id: cluster.id}, synchronize_session=False)

            # snapshot metric
            db.add(
                ClusterMetric(
                    id=uuid.uuid4(),
                    cluster_id=cluster.id,
                    avg_followers=float(avg_followers) if avg_followers else None,
                    interest_distribution=dict(interest_counts.most_common(10)),
                    computed_date=today,
                )
            )

        db.commit()
        log.info(
            "cluster_profiles_task: %d clusters, %d noise",
            result.n_clusters,
            result.n_noise,
        )
        return {"n_clusters": result.n_clusters, "n_noise": result.n_noise}

    except Exception as exc:
        db.rollback()
        log.exception("cluster_profiles_task failed")
        raise self.retry(exc=exc, countdown=120, max_retries=2) from exc
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Identity resolution
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.intelligence.resolve_identities_task", bind=True, acks_late=True
)
def resolve_identities_task(self) -> dict:
    """
    Cross-platform identity resolution.

    Compares profiles on *different* platforms using fuzzy name + bio URL
    matching.  High-confidence pairs (≥ AUTO_CONFIRM) get a UnifiedUser;
    medium-confidence pairs go to the manual review queue.

    O(n²) within each (platform_A × platform_B) pair — acceptable for Phase 3
    data volumes.  Phase 6 will add an ANN pre-filter to scale this.
    """
    from app.db.models.profile_link import ProfileLink
    from app.db.models.social_profile import SocialProfile
    from app.db.models.unified_user import UnifiedUser
    from app.intelligence.identity_resolution import AUTO_CONFIRM_THRESHOLD

    db: Session = SessionLocal()
    try:
        # Load all profiles grouped by platform
        all_profiles = db.query(SocialProfile).all()
        by_platform: dict[str, list[SocialProfile]] = {}
        for p in all_profiles:
            by_platform.setdefault(p.platform, []).append(p)

        platforms = list(by_platform.keys())
        new_links = created_users = 0

        for i, plat_a in enumerate(platforms):
            for plat_b in platforms[i + 1 :]:
                for src in by_platform[plat_a]:
                    for tgt in by_platform[plat_b]:
                        # Skip pairs already linked
                        existing = (
                            db.query(ProfileLink)
                            .filter(
                                ProfileLink.source_profile_id == src.id,
                                ProfileLink.target_profile_id == tgt.id,
                            )
                            .first()
                        )
                        if existing:
                            continue

                        match = score_pair(
                            source_id=str(src.id),
                            source_display_name=src.display_name,
                            source_username=src.username,
                            source_bio=src.bio,
                            target_id=str(tgt.id),
                            target_display_name=tgt.display_name,
                            target_username=tgt.username,
                            target_bio=tgt.bio,
                        )

                        if match is None:
                            continue

                        # Optionally auto-create UnifiedUser
                        unified_user_id = None
                        if match.status == "confirmed":
                            # Re-use existing unified_user if src already has one
                            unified_user_id = src.unified_user_id or tgt.unified_user_id
                            if unified_user_id is None:
                                uu = UnifiedUser(
                                    id=uuid.uuid4(),
                                    canonical_name=src.display_name or tgt.display_name,
                                )
                                db.add(uu)
                                db.flush()
                                unified_user_id = uu.id
                                created_users += 1

                            # Link both profiles to the unified user
                            if src.unified_user_id is None:
                                src.unified_user_id = unified_user_id
                            if tgt.unified_user_id is None:
                                tgt.unified_user_id = unified_user_id

                        db.add(
                            ProfileLink(
                                id=uuid.uuid4(),
                                unified_user_id=unified_user_id,
                                source_profile_id=src.id,
                                target_profile_id=tgt.id,
                                confidence=match.confidence,
                                match_method=match.match_method,
                                status=match.status,
                            )
                        )
                        new_links += 1

        db.commit()
        log.info(
            "resolve_identities_task: %d new links, %d unified users created",
            new_links,
            created_users,
        )
        return {"new_links": new_links, "unified_users_created": created_users}

    except Exception as exc:
        db.rollback()
        log.exception("resolve_identities_task failed")
        raise self.retry(exc=exc, countdown=120, max_retries=2) from exc
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Nightly orchestration pipeline
# ─────────────────────────────────────────────────────────────────────────────

@celery_app.task(name="app.tasks.intelligence.run_nightly_intelligence_pipeline")
def run_nightly_intelligence_pipeline() -> dict:
    """
    Ordered nightly intelligence pipeline:
      classify → cluster → resolve identities

    Uses Celery chaining so each step waits for the previous to finish.
    """
    from celery import chain

    pipeline = chain(
        classify_profiles_task.si(),
        cluster_profiles_task.si(),
        resolve_identities_task.si(),
    )
    result = pipeline.apply_async()
    log.info("Nightly intelligence pipeline started, root task_id=%s", result.id)
    return {"pipeline_task_id": result.id}
