"""
HDBSCAN audience clustering — Phase 3.

Accepts a matrix of L2-normalised 384-dim embeddings and returns cluster
assignments.  Euclidean distance on unit vectors ≈ cosine distance × √2, so
the clusters mirror semantic similarity from the sentence-transformer model.

The returned ClusteringResult is plain Python (no SQLAlchemy) so it can be
safely serialised through Celery's JSON pipeline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger(__name__)

# ── tuneable defaults ─────────────────────────────────────────────────────────
# min_cluster_size = smallest meaningful audience segment
# min_samples      = controls noise tolerance (higher → more noise points)
DEFAULT_MIN_CLUSTER_SIZE = 10
DEFAULT_MIN_SAMPLES = 5


@dataclass
class ClusteringResult:
    """Output of a single clustering run."""

    # profile_id (str) → hdbscan label (-1 means noise / unclustered)
    assignments: dict[str, int] = field(default_factory=dict)
    # hdbscan label → list of profile_ids  (excludes noise label -1)
    clusters: dict[int, list[str]] = field(default_factory=dict)
    n_clusters: int = 0
    n_noise: int = 0


def run_clustering(
    profile_ids: list[str],
    embeddings: list[list[float]],
    min_cluster_size: int = DEFAULT_MIN_CLUSTER_SIZE,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> ClusteringResult:
    """
    Run HDBSCAN on a set of profile embeddings.

    Args:
        profile_ids: Ordered list of profile UUID strings.
        embeddings:  Corresponding 384-dim float lists (L2-normalised).
        min_cluster_size: Minimum profiles per cluster.
        min_samples: HDBSCAN min_samples parameter.

    Returns:
        ClusteringResult with per-profile label assignments.
    """
    import hdbscan  # lazy import — heavy dependency, only needed at task time

    if len(profile_ids) != len(embeddings):
        raise ValueError("profile_ids and embeddings must have the same length")

    result = ClusteringResult()

    if len(profile_ids) < min_cluster_size * 2:
        log.warning(
            "Too few profiles (%d) for clustering (need ≥ %d). "
            "All assigned to noise.",
            len(profile_ids),
            min_cluster_size * 2,
        )
        result.assignments = {pid: -1 for pid in profile_ids}
        result.n_noise = len(profile_ids)
        return result

    X = np.array(embeddings, dtype=np.float32)

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        cluster_selection_method="eom",  # Excess of Mass — better for uneven densities
        prediction_data=True,
    )
    labels: np.ndarray = clusterer.fit_predict(X)

    assignments: dict[str, int] = {}
    clusters: dict[int, list[str]] = {}

    for pid, label in zip(profile_ids, labels.tolist()):
        lbl = int(label)
        assignments[pid] = lbl
        if lbl != -1:
            clusters.setdefault(lbl, []).append(pid)

    result.assignments = assignments
    result.clusters = clusters
    result.n_clusters = len(clusters)
    result.n_noise = sum(1 for lbl in assignments.values() if lbl == -1)

    log.info(
        "Clustering complete: %d clusters, %d noise points (%.1f%% coverage)",
        result.n_clusters,
        result.n_noise,
        100 * (1 - result.n_noise / len(profile_ids)),
    )
    return result


def derive_cluster_label(top_interests: list[str], max_topics: int = 3) -> str:
    """
    Build a human-readable cluster label from top interest topics.

    e.g. ["music", "entertainment", "fashion"] → "music · entertainment · fashion"
    """
    topics = top_interests[:max_topics]
    return " · ".join(t.title() for t in topics) if topics else "Uncategorised"
