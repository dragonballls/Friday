from __future__ import annotations

import pytest

from core.gods_eye_context import sanitize_spatial_context


def test_sanitizes_valid_spatial_context() -> None:
    result = sanitize_spatial_context(
        {
            "latitude": 34.052235,
            "longitude": -118.243683,
            "altitude": 120.5,
            "heading": 270,
            "object_id": " aircraft-42 ",
            "label": " Los Angeles ",
            "layers": ["aircraft", "satellites"],
        }
    )
    assert result["latitude"] == 34.052235
    assert result["longitude"] == -118.243683
    assert result["object_id"] == "aircraft-42"
    assert result["layers"] == ["aircraft", "satellites"]


def test_rejects_invalid_coordinates() -> None:
    with pytest.raises(ValueError):
        sanitize_spatial_context({"latitude": 91})
    with pytest.raises(ValueError):
        sanitize_spatial_context({"longitude": -181})


def test_rejects_boolean_numeric_values() -> None:
    with pytest.raises(ValueError):
        sanitize_spatial_context({"latitude": True})


def test_rejects_oversized_layers() -> None:
    with pytest.raises(ValueError):
        sanitize_spatial_context({"layers": ["x"] * 65})


def test_rejects_non_object_context() -> None:
    with pytest.raises(ValueError):
        sanitize_spatial_context(["not", "an", "object"])
