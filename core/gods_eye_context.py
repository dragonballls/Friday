"""Sanitize spatial context received from the optional God's Eye service.

This module is intentionally dependency-free. God's Eye is treated as an
untrusted optional producer: malformed or unexpectedly large context is
rejected instead of being allowed into Friday's conversation state.
"""

from __future__ import annotations

from typing import Any


MAX_OBJECT_ID_LENGTH = 200
MAX_LABEL_LENGTH = 300
MAX_LAYERS = 64


def sanitize_spatial_context(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("spatial context must be an object")

    result: dict[str, Any] = {}

    if "latitude" in value:
        result["latitude"] = _number(value["latitude"], -90.0, 90.0, "latitude")
    if "longitude" in value:
        result["longitude"] = _number(value["longitude"], -180.0, 180.0, "longitude")
    if "altitude" in value:
        result["altitude"] = _number(value["altitude"], -1000.0, 100000000.0, "altitude")
    if "heading" in value:
        result["heading"] = _number(value["heading"], 0.0, 360.0, "heading")
    if "object_id" in value:
        result["object_id"] = _text(value["object_id"], MAX_OBJECT_ID_LENGTH, "object_id")
    if "label" in value:
        result["label"] = _text(value["label"], MAX_LABEL_LENGTH, "label")
    if "layers" in value:
        layers = value["layers"]
        if not isinstance(layers, list) or len(layers) > MAX_LAYERS:
            raise ValueError("layers must be a list of at most 64 items")
        result["layers"] = [_text(item, 100, "layer") for item in layers]

    return result


def _number(value: Any, lower: float, upper: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
    return value


def _text(value: Any, maximum: int, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be text")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{name} is too long")
    return value
