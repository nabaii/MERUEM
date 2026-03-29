"""Tests for the lookalike scoring module (pure-logic, no DB required)."""

import pytest

from app.intelligence.lookalike import _compute_centroid


def test_centroid_single_vector():
    v = [1.0, 0.0, 0.0]
    centroid = _compute_centroid([v])
    assert centroid == pytest.approx(v)


def test_centroid_two_vectors():
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    centroid = _compute_centroid([v1, v2])
    assert centroid == pytest.approx([0.5, 0.5])


def test_centroid_preserves_dimension():
    dim = 384
    vecs = [[float(i % 10) for i in range(dim)] for _ in range(5)]
    centroid = _compute_centroid(vecs)
    assert len(centroid) == dim


def test_centroid_all_same_vectors():
    v = [0.5] * 10
    centroid = _compute_centroid([v, v, v])
    assert centroid == pytest.approx(v)
