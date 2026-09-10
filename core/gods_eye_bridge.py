"""Safe Friday-side bridge for the optional God's Eye View service.

The bridge deliberately keeps God's Eye behind a small, JSON-only capability
boundary. It does not execute shell commands, read credentials, or expose an
arbitrary URL fetch primitive.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse


DEFAULT_GODS_EYE_URL = "http://127.0.0.1:4173"


@dataclass(frozen=True)
class GodsEyeBridge:
    base_url: str = DEFAULT_GODS_EYE_URL

    def __post_init__(self) -> None:
        object.__setattr__(self, "base_url", _validate_local_url(self.base_url))

    @classmethod
    def from_environment(cls) -> "GodsEyeBridge":
        raw = os.getenv("FRIDAY_GODS_EYE_URL", DEFAULT_GODS_EYE_URL).strip()
        return cls(raw)

    def location_url(self, latitude: float, longitude: float, *, zoom: float | None = None) -> str:
        _validate_coordinate(latitude, -90.0, 90.0, "latitude")
        _validate_coordinate(longitude, -180.0, 180.0, "longitude")
        url = f"{self.base_url}/?lat={latitude:.6f}&lon={longitude:.6f}"
        if zoom is not None:
            if not 0.0 <= zoom <= 24.0:
                raise ValueError("zoom must be between 0 and 24")
            url += f"&zoom={zoom:.2f}"
        return url

    def search_url(self, place: str) -> str:
        place = place.strip()
        if not place or len(place) > 200:
            raise ValueError("place must contain 1-200 characters")
        return f"{self.base_url}/?q={quote(place, safe='')}"

    def health(self, *, timeout: float = 1.5) -> dict[str, Any]:
        """Check only the configured local God's Eye root, without sending secrets."""
        if timeout <= 0 or timeout > 10:
            raise ValueError("timeout must be between 0 and 10 seconds")
        request = Request(self.base_url + "/", method="GET", headers={"Accept": "text/html"})
        try:
            with urlopen(request, timeout=timeout) as response:
                return {"available": 200 <= response.status < 500, "status": response.status}
        except (OSError, URLError):
            return {"available": False, "status": None}

    def capability(self, name: str, **arguments: Any) -> dict[str, Any]:
        allowed = {
            "navigate_to",
            "show_route",
            "show_world_context",
            "inspect_selected_object",
            "track_object",
            "set_view",
            "get_current_view_context",
            "set_layers",
        }
        if name not in allowed:
            raise ValueError(f"unsupported God's Eye capability: {name}")
        return {"capability": name, "arguments": arguments}


def _validate_local_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("God's Eye must be bound to localhost")
    if parsed.username or parsed.password:
        raise ValueError("credentials are not permitted in God's Eye URL")
    return value.rstrip("/")


def _validate_coordinate(value: float, lower: float, upper: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not lower <= float(value) <= upper:
        raise ValueError(f"{name} must be between {lower} and {upper}")
