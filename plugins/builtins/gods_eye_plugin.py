"""Friday tools for interacting with the optional local God's Eye View UI."""

from __future__ import annotations

from core.gods_eye_bridge import GodsEyeBridge
from plugins.base import ToolPlugin


class GodsEyeNavigatePlugin(ToolPlugin):
    name = "gods_eye_navigate"
    description = "Open God's Eye at a place or coordinate without granting it arbitrary computer or network access."
    category = "spatial"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "place": {"type": "string", "description": "Place name, address, landmark, or region to view."},
                "latitude": {"type": "number", "description": "Latitude from -90 to 90."},
                "longitude": {"type": "number", "description": "Longitude from -180 to 180."},
                "zoom": {"type": "number", "description": "Optional map zoom from 0 to 24."},
            },
            "required": [],
        }

    def execute(
        self,
        place: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        zoom: float | None = None,
    ) -> dict:
        if place and (latitude is not None or longitude is not None):
            raise ValueError("provide either place or latitude/longitude, not both")
        bridge = GodsEyeBridge.from_environment()
        if place:
            url = bridge.search_url(place)
        elif latitude is not None and longitude is not None:
            url = bridge.location_url(latitude, longitude, zoom=zoom)
        else:
            raise ValueError("provide a place or both latitude and longitude")
        return {"success": True, "capability": "navigate_to", "url": url}


class GodsEyeContextPlugin(ToolPlugin):
    name = "gods_eye_capability"
    description = "Create a validated God's Eye capability request for navigation, routes, layers, tracking, or world context."
    category = "spatial"

    def get_parameters_schema(self):
        return {
            "type": "object",
            "properties": {
                "capability": {
                    "type": "string",
                    "enum": [
                        "navigate_to",
                        "show_route",
                        "show_world_context",
                        "inspect_selected_object",
                        "track_object",
                        "set_view",
                        "get_current_view_context",
                        "set_layers",
                    ],
                },
                "arguments": {"type": "object"},
            },
            "required": ["capability"],
        }

    def execute(self, capability: str, arguments: dict | None = None) -> dict:
        bridge = GodsEyeBridge.from_environment()
        return bridge.capability(capability, **(arguments or {}))
