"""Friday-side adapter for the God's Eye capability contract.

The adapter deliberately remains transport-agnostic: it creates validated
requests and consumes sanitized spatial context. A separate transport can be
added later without giving the integration direct shell, filesystem, or
credential access.
"""

from __future__ import annotations

from typing import Any

from .contract import Capability, SpatialContext, SpatialRequest, build_request


class GodsEyeAdapter:
    """Safe Friday-facing facade for God's Eye."""

    def request(
        self,
        capability: Capability,
        arguments: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> SpatialRequest:
        return build_request(capability, arguments, request_id)

    def context_from_event(self, event: dict[str, Any]) -> SpatialContext:
        """Normalize a God's Eye context event without retaining secrets."""
        if not isinstance(event, dict):
            raise TypeError("God's Eye context event must be an object")

        layers = event.get("active_layers", ())
        if not isinstance(layers, (list, tuple)):
            raise TypeError("active_layers must be a list or tuple")

        selected = event.get("selected_object")
        if selected is not None and not isinstance(selected, dict):
            raise TypeError("selected_object must be an object or null")

        return SpatialContext(
            latitude=event.get("latitude"),
            longitude=event.get("longitude"),
            altitude_m=event.get("altitude_m"),
            heading_deg=event.get("heading_deg"),
            selected_object=selected,
            active_layers=tuple(str(layer) for layer in layers),
            source="gods_eye",
        )
