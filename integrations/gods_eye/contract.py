"""Safe, transport-agnostic contract for Friday <-> God's Eye.

This module intentionally contains no network, shell, browser, or credential access.
It only validates spatial capability requests and normalizes world-context events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Capability = Literal[
    "navigate_to",
    "show_route",
    "show_world_context",
    "inspect_selected_object",
    "track_object",
    "set_view",
    "get_current_view_context",
    "set_layers",
]

_ALLOWED_CAPABILITIES: frozenset[str] = frozenset(
    {
        "navigate_to",
        "show_route",
        "show_world_context",
        "inspect_selected_object",
        "track_object",
        "set_view",
        "get_current_view_context",
        "set_layers",
    }
)


@dataclass(frozen=True, slots=True)
class SpatialRequest:
    capability: Capability
    arguments: dict[str, Any] = field(default_factory=dict)
    request_id: str | None = None

    def validate(self) -> None:
        if self.capability not in _ALLOWED_CAPABILITIES:
            raise ValueError(f"Unsupported God's Eye capability: {self.capability}")
        if not isinstance(self.arguments, dict):
            raise TypeError("God's Eye capability arguments must be an object")
        if self.request_id is not None and not self.request_id.strip():
            raise ValueError("request_id cannot be blank")


@dataclass(frozen=True, slots=True)
class SpatialContext:
    """Context returned by God's Eye; deliberately excludes credentials/secrets."""

    latitude: float | None = None
    longitude: float | None = None
    altitude_m: float | None = None
    heading_deg: float | None = None
    selected_object: dict[str, Any] | None = None
    active_layers: tuple[str, ...] = ()
    source: str = "gods_eye"

    def as_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude_m": self.altitude_m,
            "heading_deg": self.heading_deg,
            "selected_object": self.selected_object,
            "active_layers": list(self.active_layers),
            "source": self.source,
        }


def build_request(
    capability: Capability,
    arguments: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> SpatialRequest:
    request = SpatialRequest(
        capability=capability,
        arguments=dict(arguments or {}),
        request_id=request_id,
    )
    request.validate()
    return request
