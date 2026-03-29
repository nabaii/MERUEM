import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentAccount, DbDep
from app.db.models.collection_job import CollectionJob, JobStatus
from app.schemas.collection_jobs import CollectionJobCreate, CollectionJobOut
from app.tasks.collection import run_collection_job

router = APIRouter(prefix="/collection-jobs", tags=["collection"])


@router.post("", response_model=CollectionJobOut, status_code=status.HTTP_202_ACCEPTED)
def create_collection_job(payload: CollectionJobCreate, account: CurrentAccount, db: DbDep):
    job = CollectionJob(
        id=uuid.uuid4(),
        platform=payload.platform,
        params=payload.params,
        created_by=account.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch async Celery task
    task = run_collection_job.apply_async(args=[str(job.id)], queue="collection")
    job.celery_task_id = task.id
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[CollectionJobOut])
def list_jobs(account: CurrentAccount, db: DbDep, limit: int = 20):
    return (
        db.query(CollectionJob)
        .order_by(CollectionJob.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/{job_id}", response_model=CollectionJobOut)
def get_job(job_id: UUID, _: CurrentAccount, db: DbDep):
    job = db.query(CollectionJob).filter(CollectionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job
