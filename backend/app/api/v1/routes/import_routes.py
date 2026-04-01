"""
FastAPI routes for manual data import and URL enrichment.
Supports CSV/Excel upload, bulk URL enrichment, and proxy/session pool management.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_account
from app.core.celery_app import celery_app
from app.db.models.account import Account
from app.db.models.collection_job import CollectionJob, JobStatus
from app.db.session import get_db
from app.schemas.import_schema import (
    BulkUrlEnrichRequest,
    ImportJobOut,
    ImportResultOut,
    ProxyAddRequest,
    ProxyStatsOut,
    SessionAddRequest,
    SessionStatsOut,
    UrlEnrichRequest,
)

router = APIRouter(prefix="/import", tags=["import"])


# ── CSV / Excel upload ────────────────────────────────────────────────────────


@router.post(
    "/csv",
    response_model=ImportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a CSV or Excel file for bulk profile import",
)
async def upload_csv(
    file: Annotated[UploadFile, File(description="CSV or Excel file (.csv / .xlsx / .xls)")],
    default_platform: Annotated[
        str,
        Form(description="Default platform if not specified in the file"),
    ] = "unknown",
    enrich_via_bot: Annotated[
        bool,
        Form(description="Bot-enrich rows that include a profile_url"),
    ] = False,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ImportJobOut:
    """
    Accept a CSV or Excel file, create an async import job, and return immediately.
    Poll `/import/jobs/{id}` for progress.

    **Recognised CSV columns** (flexible matching):
    `username`, `platform`, `display_name`, `bio`, `follower_count`,
    `following_count`, `location`, `profile_url`, `profile_image_url`, `email`, `phone`
    """
    if not file.filename or not file.filename.lower().endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .csv, .xlsx, and .xls files are supported",
        )

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:  # 20 MB cap
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File size exceeds the 20 MB limit",
        )

    job = CollectionJob(
        id=uuid.uuid4(),
        platform="manual",
        status=JobStatus.pending,
        params={
            "file_content": list(file_bytes),   # JSON-serialisable bytes via list
            "filename": file.filename,
            "default_platform": default_platform,
            "enrich_via_bot": enrich_via_bot,
        },
        created_by=current_account.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.tasks.import_tasks import run_csv_import_job
    task = run_csv_import_job.apply_async(args=[str(job.id)], queue="collection")
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    db.refresh(job)

    return ImportJobOut.model_validate(job)


# ── URL enrichment ────────────────────────────────────────────────────────────


@router.post(
    "/enrich-url",
    response_model=ImportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enrich a single social media profile URL via bot scraping",
)
def enrich_single_url(
    payload: UrlEnrichRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ImportJobOut:
    """
    Visit a social media profile URL using a stealth browser and persist the scraped data.
    Supports TikTok, LinkedIn, Instagram, Twitter/X, and Facebook URLs.
    """
    job = CollectionJob(
        id=uuid.uuid4(),
        platform="manual",
        status=JobStatus.pending,
        params={"urls": [payload.url], "use_proxy": True},
        created_by=current_account.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.tasks.import_tasks import run_url_enrich_job
    task = run_url_enrich_job.apply_async(args=[str(job.id)], queue="collection")
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    db.refresh(job)

    return ImportJobOut.model_validate(job)


@router.post(
    "/enrich-urls",
    response_model=ImportJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enrich multiple profile URLs in a single batch job",
)
def enrich_bulk_urls(
    payload: BulkUrlEnrichRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ImportJobOut:
    """Batch URL enrichment. Max 200 URLs per request."""
    job = CollectionJob(
        id=uuid.uuid4(),
        platform="manual",
        status=JobStatus.pending,
        params={"urls": payload.urls[:200], "use_proxy": payload.use_proxy},
        created_by=current_account.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.tasks.import_tasks import run_url_enrich_job
    task = run_url_enrich_job.apply_async(args=[str(job.id)], queue="collection")
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    db.refresh(job)

    return ImportJobOut.model_validate(job)


# ── Job status ────────────────────────────────────────────────────────────────


@router.get(
    "/jobs",
    response_model=list[ImportJobOut],
    summary="List manual import jobs",
)
def list_import_jobs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[ImportJobOut]:
    jobs = (
        db.query(CollectionJob)
        .filter(CollectionJob.platform == "manual")
        .order_by(CollectionJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [ImportJobOut.model_validate(j) for j in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=ImportJobOut,
    summary="Get a single import job by ID",
)
def get_import_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ImportJobOut:
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job or job.platform != "manual":
        raise HTTPException(status_code=404, detail="Import job not found")
    return ImportJobOut.model_validate(job)


# ── Proxy pool management ─────────────────────────────────────────────────────


@router.post(
    "/proxies",
    status_code=status.HTTP_201_CREATED,
    summary="Add a proxy to the pool",
)
def add_proxy(
    payload: ProxyAddRequest,
    current_account: Account = Depends(get_current_account),
) -> dict:
    """
    Register a new proxy URL in the Redis-backed pool.
    Example URL formats:
    - `socks5://user:pass@host:port`
    - `http://user:pass@host:port`
    """
    from app.collectors.proxy_pool import proxy_pool
    entry = proxy_pool.add_proxy_from_url(
        url=payload.url,
        carrier=payload.carrier,
        proxy_type=payload.proxy_type,
    )
    return {"id": entry.id, "carrier": entry.carrier, "type": entry.proxy_type}


@router.get(
    "/proxies/stats",
    response_model=ProxyStatsOut,
    summary="Get proxy pool statistics",
)
def proxy_stats(current_account: Account = Depends(get_current_account)) -> ProxyStatsOut:
    from app.collectors.proxy_pool import proxy_pool
    return ProxyStatsOut(**proxy_pool.pool_stats())


@router.delete(
    "/proxies/{proxy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a proxy from the pool",
)
def remove_proxy(
    proxy_id: str,
    current_account: Account = Depends(get_current_account),
) -> None:
    from app.collectors.proxy_pool import proxy_pool
    proxy_pool.remove_proxy(proxy_id)


@router.post(
    "/proxies/{proxy_id}/reset",
    summary="Reset failure count and reactivate a proxy",
)
def reset_proxy(
    proxy_id: str,
    current_account: Account = Depends(get_current_account),
) -> dict:
    from app.collectors.proxy_pool import proxy_pool
    proxy_pool.reset_proxy(proxy_id)
    return {"status": "reset", "proxy_id": proxy_id}


# ── Session pool management ───────────────────────────────────────────────────


@router.post(
    "/sessions",
    status_code=status.HTTP_201_CREATED,
    summary="Register a pre-authenticated browser session",
)
def add_session(
    payload: SessionAddRequest,
    current_account: Account = Depends(get_current_account),
) -> dict:
    """
    Store authenticated session cookies so bot scrapers can bypass login walls.
    Obtain cookies by running `context.cookies()` in a Playwright script after login.
    """
    from app.collectors.proxy_pool import proxy_pool
    entry = proxy_pool.save_page_session(
        platform=payload.platform,
        cookies=payload.cookies,
        user_agent=payload.user_agent,
        proxy_id=payload.proxy_id,
        account_age_days=payload.account_age_days,
    )
    return {"id": entry.id, "platform": entry.platform}


@router.get(
    "/sessions/stats",
    response_model=SessionStatsOut,
    summary="Get session pool statistics",
)
def session_stats(current_account: Account = Depends(get_current_account)) -> SessionStatsOut:
    from app.collectors.proxy_pool import proxy_pool
    return SessionStatsOut(**proxy_pool.session_stats())


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Invalidate a browser session",
)
def invalidate_session(
    session_id: str,
    current_account: Account = Depends(get_current_account),
) -> None:
    from app.collectors.proxy_pool import proxy_pool
    proxy_pool.invalidate_session(session_id)
