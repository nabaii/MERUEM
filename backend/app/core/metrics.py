"""
Prometheus metrics for the Meruem API.

Exposes:
  http_requests_total        — counter by method, path, status_code
  http_request_duration_seconds — histogram by method, path
  celery_tasks_total         — counter by task_name, status (success/failure)
"""

from __future__ import annotations

import time

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

CELERY_TASK_COUNT = Counter(
    "celery_tasks_total",
    "Total Celery task executions",
    ["task_name", "status"],
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record request count and latency for every HTTP request."""

    # Normalise long IDs in paths so cardinality stays manageable
    _SKIP_PATHS = {"/metrics", "/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Don't instrument internal/observability endpoints
        if path in self._SKIP_PATHS:
            return await call_next(request)

        # Collapse UUIDs and integers to keep cardinality low
        normalised = _normalise_path(path)

        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        REQUEST_COUNT.labels(
            method=request.method,
            path=normalised,
            status_code=str(response.status_code),
        ).inc()
        REQUEST_LATENCY.labels(method=request.method, path=normalised).observe(duration)

        return response


def _normalise_path(path: str) -> str:
    """Replace UUID and integer path segments with placeholders."""
    import re
    path = re.sub(
        r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "/{id}",
        path,
    )
    path = re.sub(r"/\d+", "/{id}", path)
    return path
