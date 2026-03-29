from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbDep

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(db: DbDep):
    """Liveness + readiness check."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "service": "meruem-api"}


@router.get("/health/db")
def db_health(db: DbDep):
    """Confirm PostgreSQL + pgvector are reachable."""
    result = db.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")).fetchone()
    pgvector_version = result[0] if result else None
    return {
        "status": "ok",
        "postgresql": "connected",
        "pgvector": pgvector_version or "not installed",
    }
