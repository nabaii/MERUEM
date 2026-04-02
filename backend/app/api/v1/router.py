from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    campaigns,
    clusters,
    collection_jobs,
    discovery,
    health,
    identity,
    import_routes,
    lookalike,
    notifications,
    processing,
    profiling,
    profiles,
    stats,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(profiles.router)
api_router.include_router(collection_jobs.router)
api_router.include_router(processing.router)
# Phase 3 — intelligence
api_router.include_router(clusters.router)
api_router.include_router(lookalike.router)
api_router.include_router(identity.router)
api_router.include_router(stats.router)
# Phase 5 — campaigns & notifications
api_router.include_router(campaigns.router)
api_router.include_router(notifications.router)
# Phase 7 — multi-source ingestion (bot + manual import)
api_router.include_router(import_routes.router)
# Phase 8 — profiling pipeline
api_router.include_router(profiling.router)
# Phase 9 — platform-specific user discovery
api_router.include_router(discovery.router)
