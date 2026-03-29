"""Tests for the HDBSCAN clustering engine."""

import random

import numpy as np
import pytest

from app.intelligence.clustering import (
    ClusteringResult,
    derive_cluster_label,
    run_clustering,
)


def _random_unit_vector(dim: int = 384) -> list[float]:
    v = np.random.randn(dim).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


def _cluster_of_vectors(n: int, dim: int = 384, noise: float = 0.05) -> list[list[float]]:
    """Return n similar vectors around a random centroid."""
    center = np.random.randn(dim).astype(np.float32)
    center /= np.linalg.norm(center)
    vecs = []
    for _ in range(n):
        perturb = np.random.randn(dim).astype(np.float32) * noise
        v = center + perturb
        v /= np.linalg.norm(v)
        vecs.append(v.tolist())
    return vecs


def test_too_few_profiles_returns_all_noise():
    ids = [f"p{i}" for i in range(5)]
    embeddings = [_random_unit_vector() for _ in range(5)]
    result = run_clustering(ids, embeddings, min_cluster_size=10)
    assert all(v == -1 for v in result.assignments.values())
    assert result.n_clusters == 0
    assert result.n_noise == 5


def test_finds_clusters_in_structured_data():
    """Three tight groups + noise should produce ≥ 2 clusters."""
    ids = []
    embeddings = []
    for group in range(3):
        group_vecs = _cluster_of_vectors(20)
        for j, v in enumerate(group_vecs):
            ids.append(f"g{group}_p{j}")
            embeddings.append(v)

    result = run_clustering(ids, embeddings, min_cluster_size=5, min_samples=3)
    assert result.n_clusters >= 2


def test_assignments_cover_all_ids():
    ids = [f"p{i}" for i in range(30)]
    embeddings = _cluster_of_vectors(30)
    result = run_clustering(ids, embeddings, min_cluster_size=5)
    assert set(result.assignments.keys()) == set(ids)


def test_clusters_dict_excludes_noise():
    ids = [f"p{i}" for i in range(50)]
    embeddings = _cluster_of_vectors(50)
    result = run_clustering(ids, embeddings)
    for label in result.clusters:
        assert label != -1


def test_mismatched_lengths_raises():
    with pytest.raises(ValueError, match="same length"):
        run_clustering(["p1", "p2"], [_random_unit_vector()])


def test_derive_cluster_label_formats_correctly():
    assert derive_cluster_label(["music", "entertainment", "fashion"]) == (
        "Music · Entertainment · Fashion"
    )


def test_derive_cluster_label_empty():
    assert derive_cluster_label([]) == "Uncategorised"


def test_derive_cluster_label_truncates_to_max():
    topics = ["a", "b", "c", "d", "e"]
    label = derive_cluster_label(topics, max_topics=3)
    assert label.count("·") == 2
