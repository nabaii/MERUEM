"""Celery tasks for the Ghost Virality scouting pipeline.

Task graph per scout job:
  run_ghost_scout_job
    └─ _scrape_competitor_reels   (Playwright stealth scrape, t0 pass)
    └─ run_ghost_analytics        (compute filters after t1 pass)
         └─ run_ghost_pattern_recognition  (per flagged post)
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from celery import Task

from app.core.celery_app import celery_app
from app.db.models.ghost_virality import (
    GhostJobStatus,
    GhostPatternCard,
    GhostReelSnapshot,
    GhostScoutJob,
    GhostViralPost,
    AudioType,
)
from app.db.session import SessionLocal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scout Job — orchestrator
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="app.tasks.ghost_virality.run_ghost_scout_job", max_retries=2)
def run_ghost_scout_job(self: Task, job_id: str) -> dict:
    """Main orchestrator for a single Ghost Virality scouting run.

    Pass 0 (t0): scrape all competitor accounts, store snapshots.
    After a configured delay, pass 1 (t1) is dispatched automatically
    for velocity calculation.
    """
    db = SessionLocal()
    try:
        job = db.query(GhostScoutJob).filter(GhostScoutJob.id == uuid.UUID(job_id)).first()
        if not job:
            log.error("GhostScoutJob %s not found", job_id)
            return {"error": "job not found"}

        job.status = GhostJobStatus.running
        job.started_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        accounts: list[str] = job.competitor_accounts or []
        if not accounts:
            log.warning("GhostScoutJob %s has no competitor_accounts", job_id)
            job.status = GhostJobStatus.completed
            job.completed_at = datetime.now(timezone.utc)
            db.add(job)
            db.commit()
            return {"job_id": job_id, "reels_scraped": 0}

        total_scraped = 0
        for account in accounts:
            count = _scrape_account_reels(account, job.niche, job_id, pass_index=0, db=db)
            total_scraped += count

        job.reels_scraped = total_scraped
        db.add(job)
        db.commit()
        log.info("GhostScoutJob %s t0 pass: %d reels scraped", job_id, total_scraped)

        # Schedule t1 pass (velocity snapshot) in ~4 hours
        run_ghost_velocity_pass.apply_async(
            args=[job_id],
            countdown=4 * 3600,
            queue="ghost_scout",
        )

        return {"job_id": job_id, "reels_scraped": total_scraped, "t1_scheduled": True}

    except Exception as exc:
        log.exception("GhostScoutJob %s failed: %s", job_id, exc)
        try:
            job = db.query(GhostScoutJob).filter(GhostScoutJob.id == uuid.UUID(job_id)).first()
            if job:
                job.status = GhostJobStatus.failed
                job.error_message = str(exc)[:2000]
                job.completed_at = datetime.now(timezone.utc)
                db.add(job)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Velocity pass (t1)
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="app.tasks.ghost_virality.run_ghost_velocity_pass", max_retries=2)
def run_ghost_velocity_pass(self: Task, job_id: str) -> dict:
    """Second scrape pass (t1) for a scout job — enables velocity calculation."""
    db = SessionLocal()
    try:
        job = db.query(GhostScoutJob).filter(GhostScoutJob.id == uuid.UUID(job_id)).first()
        if not job:
            return {"error": "job not found"}

        accounts: list[str] = job.competitor_accounts or []
        total_scraped = 0
        for account in accounts:
            count = _scrape_account_reels(account, job.niche, job_id, pass_index=1, db=db)
            total_scraped += count

        log.info("GhostScoutJob %s t1 pass: %d reels scraped", job_id, total_scraped)

        # Trigger analytics computation
        run_ghost_analytics.apply_async(args=[job_id], queue="ghost_analytics")

        return {"job_id": job_id, "reels_scraped_t1": total_scraped}

    except Exception as exc:
        log.exception("GhostScoutJob %s t1 pass failed: %s", job_id, exc)
        raise self.retry(exc=exc, countdown=120)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Analytics — apply Ghost Virality filters
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="app.tasks.ghost_virality.run_ghost_analytics", max_retries=2)
def run_ghost_analytics(self: Task, job_id: str) -> dict:
    """Apply Outlier Reach + Ghost Virality Delta filters to all snapshots in a job.

    For each reel with both t0 and t1 snapshots, evaluate filters and
    upsert GhostViralPost if it qualifies.
    """
    from app.services.ghost_virality_analytics import (
        flag_ghost_viral,
        refresh_niche_percentiles,
        check_niche_drift,
    )

    db = SessionLocal()
    try:
        job = db.query(GhostScoutJob).filter(GhostScoutJob.id == uuid.UUID(job_id)).first()
        if not job:
            return {"error": "job not found"}

        niche = job.niche

        # Refresh percentile distribution for this niche
        percentile_row = refresh_niche_percentiles(niche, db)

        # Get all distinct reel_ids in this job
        reel_ids = (
            db.query(GhostReelSnapshot.reel_id)
            .filter(GhostReelSnapshot.scout_job_id == uuid.UUID(job_id))
            .distinct()
            .all()
        )

        ghost_count = 0
        for (reel_id,) in reel_ids:
            snap_t0 = (
                db.query(GhostReelSnapshot)
                .filter(
                    GhostReelSnapshot.reel_id == reel_id,
                    GhostReelSnapshot.scout_job_id == uuid.UUID(job_id),
                    GhostReelSnapshot.pass_index == 0,
                )
                .first()
            )
            snap_t1 = (
                db.query(GhostReelSnapshot)
                .filter(
                    GhostReelSnapshot.reel_id == reel_id,
                    GhostReelSnapshot.scout_job_id == uuid.UUID(job_id),
                    GhostReelSnapshot.pass_index == 1,
                )
                .first()
            )

            if snap_t0 is None:
                continue

            result = flag_ghost_viral(snap_t0, snap_t1, percentile_row, db)
            if result:
                ghost_count += 1
                # Dispatch pattern recognition asynchronously
                run_ghost_pattern_recognition.apply_async(
                    args=[str(result.id)],
                    queue="ghost_pattern",
                )

        # Update job counts
        job.ghost_viral_found = ghost_count
        job.status = GhostJobStatus.completed
        job.completed_at = datetime.now(timezone.utc)
        db.add(job)
        db.commit()

        # Niche drift check — log warning if drift detected
        drift = check_niche_drift(niche, db)
        if drift:
            log.warning("NICHE DRIFT DETECTED: %s", drift["message"])

        log.info("GhostScoutJob %s analytics complete: %d ghost viral posts", job_id, ghost_count)
        return {"job_id": job_id, "ghost_viral_found": ghost_count}

    except Exception as exc:
        log.exception("Ghost analytics for job %s failed: %s", job_id, exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pattern Recognition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="app.tasks.ghost_virality.run_ghost_pattern_recognition",
    max_retries=2,
)
def run_ghost_pattern_recognition(self: Task, ghost_post_id: str) -> dict:
    """Extract hook, transcript, OCR text, and audio type for a Ghost Viral post.

    This task runs Whisper (local), PySceneDetect, and TrOCR/Tesseract on the
    downloaded Reel. Falls back to metadata-only pattern card if video is
    unavailable (e.g., download failed or model not installed).
    """
    db = SessionLocal()
    try:
        post = (
            db.query(GhostViralPost)
            .filter(GhostViralPost.id == uuid.UUID(ghost_post_id))
            .first()
        )
        if not post:
            log.error("GhostViralPost %s not found", ghost_post_id)
            return {"error": "post not found"}

        # Check if a pattern card already exists
        existing_card = (
            db.query(GhostPatternCard)
            .filter(GhostPatternCard.ghost_post_id == post.id)
            .first()
        )
        if existing_card:
            log.debug("Pattern card already exists for post %s", ghost_post_id)
            return {"ghost_post_id": ghost_post_id, "status": "already_exists"}

        card_data = _build_pattern_card(post)

        card = GhostPatternCard(
            id=uuid.uuid4(),
            ghost_post_id=post.id,
            hook_duration_seconds=card_data.get("hook_duration_seconds"),
            hook_clip_path=card_data.get("hook_clip_path"),
            scene_cut_count=card_data.get("scene_cut_count"),
            transcript_snippet=card_data.get("transcript_snippet"),
            transcript_language=card_data.get("transcript_language"),
            transcript_confidence=card_data.get("transcript_confidence"),
            visual_text=card_data.get("visual_text"),
            audio_type=card_data.get("audio_type", AudioType.unknown),
            audio_id=card_data.get("audio_id"),
            audio_name=card_data.get("audio_name"),
            raw_card=card_data,
        )
        db.add(card)

        post.pattern_card_ready = True
        db.add(post)
        db.commit()

        # Attempt to assign hook archetype after 50+ cards
        _maybe_assign_hook_archetypes(db)

        log.info("Pattern card created for GhostViralPost %s", ghost_post_id)
        return {"ghost_post_id": ghost_post_id, "status": "created"}

    except Exception as exc:
        log.exception("Pattern recognition failed for post %s: %s", ghost_post_id, exc)
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Scraper helper — Playwright stealth (Sprint 1)
# ---------------------------------------------------------------------------


def _scrape_account_reels(
    account_username: str,
    niche: str,
    job_id: str,
    pass_index: int,
    db,
) -> int:
    """Scrape public Reel metadata from an Instagram account.

    Uses Playwright with stealth plugin + residential proxy rotation.
    Implements exponential backoff on rate-limit detection.

    Returns the number of Reels successfully scraped.
    """
    from app.core.config import settings

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.warning("Playwright not installed — using mock data for ghost scout")
        return _mock_scrape(account_username, niche, job_id, pass_index, db)

    reels_scraped = 0
    max_retries = 3

    for attempt in range(max_retries):
        try:
            with sync_playwright() as pw:
                proxy_config = _get_proxy_config(settings)
                browser = pw.chromium.launch(
                    headless=settings.bot_headless,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    ),
                    proxy=proxy_config,
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                page = context.new_page()

                url = f"https://www.instagram.com/{account_username}/reels/"
                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Detect soft-blocks
                if _is_soft_blocked(page):
                    log.warning("Soft-block detected for %s — backing off", account_username)
                    browser.close()
                    time.sleep(random.uniform(30, 90))
                    continue

                # Random delay to mimic human browsing
                time.sleep(random.uniform(2, 7))

                reels_data = _extract_reels_metadata(page, account_username)
                browser.close()

                for reel in reels_data:
                    snapshot = GhostReelSnapshot(
                        id=uuid.uuid4(),
                        reel_id=reel.get("reel_id", ""),
                        account_username=account_username,
                        niche=niche,
                        view_count=reel.get("view_count"),
                        like_count=reel.get("like_count"),
                        comment_count=reel.get("comment_count"),
                        follower_count=reel.get("follower_count"),
                        posted_at=reel.get("posted_at"),
                        thumbnail_url=reel.get("thumbnail_url"),
                        permalink=reel.get("permalink"),
                        audio_id=reel.get("audio_id"),
                        raw_json=reel,
                        pass_index=pass_index,
                        scout_job_id=uuid.UUID(job_id),
                    )
                    db.add(snapshot)
                    reels_scraped += 1

                db.commit()
                return reels_scraped

        except Exception as exc:
            wait = (2 ** attempt) * random.uniform(1, 3)
            log.warning(
                "Scrape attempt %d for %s failed: %s — retrying in %.1fs",
                attempt + 1, account_username, exc, wait,
            )
            time.sleep(wait)

    log.error("All scrape attempts exhausted for %s", account_username)
    return reels_scraped


def _get_proxy_config(settings) -> Optional[dict]:
    """Return Playwright proxy config if proxy is enabled."""
    if not settings.bot_use_proxy:
        return None
    proxy_url = getattr(settings, "ghost_proxy_url", "")
    if not proxy_url:
        return None
    return {"server": proxy_url}


def _is_soft_blocked(page) -> bool:
    """Detect Instagram soft-blocks (captcha, login wall, empty response)."""
    try:
        url = page.url
        content = page.content()
        if "challenge" in url or "accounts/login" in url:
            return True
        if "captcha" in content.lower():
            return True
        return False
    except Exception:
        return False


def _extract_reels_metadata(page, account_username: str) -> list[dict]:
    """Extract Reel metadata from an Instagram reels page using JavaScript evaluation."""
    try:
        reels = page.evaluate("""() => {
            const items = [];
            const articles = document.querySelectorAll('article');
            articles.forEach(article => {
                const link = article.querySelector('a[href*="/reel/"]');
                const img = article.querySelector('img');
                if (!link) return;
                const href = link.getAttribute('href') || '';
                const reelId = href.replace('/reel/', '').replace('/', '');
                items.push({
                    reel_id: reelId,
                    permalink: 'https://www.instagram.com' + href,
                    thumbnail_url: img ? img.getAttribute('src') : null,
                });
            });
            return items;
        }""")
        return reels or []
    except Exception as exc:
        log.warning("Metadata extraction failed for %s: %s", account_username, exc)
        return []


def _mock_scrape(
    account_username: str,
    niche: str,
    job_id: str,
    pass_index: int,
    db,
) -> int:
    """Fallback mock scraper used in dev environments without Playwright.

    Generates synthetic reel snapshots so the analytics pipeline can be
    exercised end-to-end without a live Instagram session.
    """
    import hashlib

    mock_reels = []
    for i in range(10):
        reel_id = hashlib.md5(f"{account_username}-{i}".encode()).hexdigest()[:12]
        follower_count = random.randint(5_000, 500_000)
        # Roughly 2 out of 10 mock reels will pass the ghost viral filters
        is_ghost = i < 2
        view_count = follower_count * (random.randint(25, 80) if is_ghost else random.randint(1, 10))
        like_count = max(1, int(view_count / (random.randint(80, 200) if is_ghost else random.randint(5, 20))))
        mock_reels.append({
            "reel_id": reel_id,
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": random.randint(0, 100),
            "follower_count": follower_count,
            "permalink": f"https://www.instagram.com/reel/{reel_id}/",
            "thumbnail_url": None,
            "audio_id": f"audio_{random.randint(1, 50)}" if random.random() > 0.5 else None,
        })

    for reel in mock_reels:
        snapshot = GhostReelSnapshot(
            id=uuid.uuid4(),
            reel_id=reel["reel_id"],
            account_username=account_username,
            niche=niche,
            view_count=reel["view_count"] + (pass_index * random.randint(100, 5000)),
            like_count=reel["like_count"] + (pass_index * random.randint(0, 10)),
            comment_count=reel["comment_count"],
            follower_count=reel["follower_count"],
            permalink=reel["permalink"],
            thumbnail_url=reel["thumbnail_url"],
            audio_id=reel["audio_id"],
            raw_json=reel,
            pass_index=pass_index,
            scout_job_id=uuid.UUID(job_id),
        )
        db.add(snapshot)
    db.commit()
    return len(mock_reels)


# ---------------------------------------------------------------------------
# Pattern card builder
# ---------------------------------------------------------------------------


def _build_pattern_card(post: GhostViralPost) -> dict:
    """Build the pattern card data for a Ghost Viral post.

    Attempts video analysis via PySceneDetect + Whisper + TrOCR.
    Falls back gracefully if libraries/video are unavailable.
    """
    card: dict = {
        "reel_id": post.reel_id,
        "account_username": post.account_username,
        "permalink": post.permalink,
    }

    # ---- Audio type determination
    # In production, this cross-references a trending audio lookup table.
    # Here we rely on whether an audio_id was captured in the snapshot.
    snapshot = None  # retrieved below if available
    audio_id = _get_audio_id_for_post(post)
    if audio_id:
        card["audio_id"] = audio_id
        card["audio_type"] = AudioType.trending  # conservative: if audio tracked, assume trending
    else:
        card["audio_type"] = AudioType.original

    # ---- Hook extraction via PySceneDetect (optional dependency)
    try:
        import scenedetect  # noqa: F401
        hook_data = _extract_hook_scenedetect(post)
        card.update(hook_data)
    except ImportError:
        log.debug("PySceneDetect not installed — skipping hook extraction")
        card["hook_duration_seconds"] = None
        card["scene_cut_count"] = None

    # ---- Transcript via Whisper (optional dependency)
    try:
        import whisper  # noqa: F401
        transcript_data = _transcribe_whisper(post)
        card.update(transcript_data)
    except ImportError:
        log.debug("Whisper not installed — skipping transcription")

    # ---- On-screen text via Tesseract (optional dependency)
    try:
        import pytesseract  # noqa: F401
        ocr_text = _extract_ocr_text(post)
        card["visual_text"] = ocr_text
    except ImportError:
        log.debug("pytesseract not installed — skipping OCR")

    return card


def _get_audio_id_for_post(post: GhostViralPost) -> Optional[str]:
    """Retrieve audio_id from the most recent snapshot for this reel."""
    db = SessionLocal()
    try:
        snap = (
            db.query(GhostReelSnapshot.audio_id)
            .filter(GhostReelSnapshot.reel_id == post.reel_id)
            .filter(GhostReelSnapshot.audio_id.isnot(None))
            .first()
        )
        return snap.audio_id if snap else None
    finally:
        db.close()


def _extract_hook_scenedetect(post: GhostViralPost) -> dict:
    """Extract hook segment using PySceneDetect (Sprint 3).

    Looks for the downloaded reel file in the configured storage path.
    Returns hook metadata dict.
    """
    from app.core.config import settings
    import os

    video_path = os.path.join(
        settings.local_raw_data_dir, "ghost_reels", f"{post.reel_id}.mp4"
    )
    if not os.path.exists(video_path):
        return {}

    try:
        from scenedetect import detect, AdaptiveDetector, split_video_ffmpeg
        scene_list = detect(video_path, AdaptiveDetector())
        scene_count = len(scene_list)
        hook_end = scene_list[0][1].get_seconds() if scene_list else 3.0
        return {
            "hook_duration_seconds": round(hook_end, 2),
            "scene_cut_count": scene_count,
        }
    except Exception as exc:
        log.warning("PySceneDetect error for %s: %s", post.reel_id, exc)
        return {}


def _transcribe_whisper(post: GhostViralPost) -> dict:
    """Transcribe audio track using local Whisper model (Sprint 3)."""
    from app.core.config import settings
    import os

    audio_path = os.path.join(
        settings.local_raw_data_dir, "ghost_reels", f"{post.reel_id}.mp3"
    )
    if not os.path.exists(audio_path):
        return {}

    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language=None)
        text = (result.get("text") or "").strip()
        lang = result.get("language", "en")
        return {
            "transcript_snippet": text[:500] if text else None,
            "transcript_language": lang,
        }
    except Exception as exc:
        log.warning("Whisper transcription error for %s: %s", post.reel_id, exc)
        return {}


def _extract_ocr_text(post: GhostViralPost) -> Optional[str]:
    """Extract on-screen text from key frames using Tesseract OCR (Sprint 3)."""
    from app.core.config import settings
    import os

    frame_dir = os.path.join(settings.local_raw_data_dir, "ghost_frames", post.reel_id)
    if not os.path.isdir(frame_dir):
        return None

    texts = []
    try:
        import pytesseract
        from PIL import Image

        for fname in sorted(os.listdir(frame_dir))[:3]:
            fpath = os.path.join(frame_dir, fname)
            try:
                img = Image.open(fpath)
                text = pytesseract.image_to_string(img).strip()
                if text:
                    texts.append(text)
            except Exception:
                continue
    except Exception as exc:
        log.warning("OCR error for %s: %s", post.reel_id, exc)

    return " | ".join(texts) if texts else None


# ---------------------------------------------------------------------------
# Hook archetype clustering (runs after 50+ pattern cards)
# ---------------------------------------------------------------------------


def _maybe_assign_hook_archetypes(db) -> None:
    """Run K-means clustering on pattern card features to assign hook archetypes.

    Only executes once >= 50 cards are available. Silently skips otherwise.
    """
    try:
        from sklearn.cluster import KMeans
        import numpy as np
    except ImportError:
        return

    cards = db.query(GhostPatternCard).filter(
        GhostPatternCard.hook_duration_seconds.isnot(None)
    ).all()

    if len(cards) < 50:
        return

    features = []
    for c in cards:
        features.append([
            c.hook_duration_seconds or 0,
            c.scene_cut_count or 0,
            1 if c.visual_text else 0,
            1 if c.audio_type == AudioType.trending else 0,
        ])

    X = np.array(features, dtype=float)

    # Normalize
    X_norm = (X - X.mean(axis=0)) / (X.std(axis=0) + 1e-8)

    n_clusters = min(5, len(cards) // 10)
    km = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
    labels = km.fit_predict(X_norm)

    archetype_names = ["Shock Cut", "Slow Reveal", "Text-First", "Audio-Lead", "Fast Edit"]

    for card, label in zip(cards, labels):
        archetype = archetype_names[label % len(archetype_names)]
        if card.hook_archetype != archetype:
            card.hook_archetype = archetype
            db.add(card)

    db.commit()
    log.info("Hook archetypes assigned to %d pattern cards", len(cards))


# ---------------------------------------------------------------------------
# Scheduled periodic scout (Celery Beat)
# ---------------------------------------------------------------------------


@celery_app.task(name="app.tasks.ghost_virality.run_scheduled_ghost_scout")
def run_scheduled_ghost_scout() -> None:
    """Celery Beat entry point — creates scout jobs for all configured niches.

    Niche + competitor list should be seeded via the admin panel or .env.
    """
    from app.core.config import settings

    niches = getattr(settings, "ghost_scout_niches", [])
    if not niches:
        log.debug("No ghost_scout_niches configured — skipping scheduled scout")
        return

    db = SessionLocal()
    try:
        for niche_cfg in niches:
            niche = niche_cfg.get("niche", "")
            accounts = niche_cfg.get("accounts", [])
            if not niche or not accounts:
                continue

            job = GhostScoutJob(
                id=uuid.uuid4(),
                niche=niche,
                competitor_accounts=accounts,
                status=GhostJobStatus.pending,
            )
            db.add(job)
            db.commit()

            run_ghost_scout_job.apply_async(args=[str(job.id)], queue="ghost_scout")
            log.info("Scheduled ghost scout job %s for niche '%s'", job.id, niche)
    finally:
        db.close()
