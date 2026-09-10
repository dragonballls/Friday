"""Deterministic intent hints for routing common spatial requests to God's Eye.

This is deliberately conservative: it produces a capability hint, not an action.
The normal Friday tool policy still decides whether/how to execute the capability.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GodsEyeIntent:
    capability: str
    confidence: float


_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("show_route", ("route", "directions", "how do i get", "get me to", "navigate to")),
    ("show_world_context", ("what is around", "what's around", "around this area", "overview of")),
    ("inspect_selected_object", ("what am i looking at", "what is that", "identify this")),
    ("track_object", ("track that", "follow that", "keep tracking")),
    ("set_layers", ("show aircraft", "show planes", "show ships", "show satellites", "show earthquakes", "show cameras")),
    # Keep location navigation deliberately specific. A generic "show me" or
    # "go to" is too broad and could steal an unrelated Friday request.
    ("navigate_to", ("show me this location", "show me the location", "show me where", "take me to", "open this location")),
)


def classify_spatial_request(text: str) -> GodsEyeIntent | None:
    """Return a conservative God's Eye capability hint for a user request."""
    normalized = " ".join(text.lower().split())
    if not normalized:
        return None
    for capability, phrases in _PATTERNS:
        if any(phrase in normalized for phrase in phrases):
            return GodsEyeIntent(capability=capability, confidence=0.75)
    return None
