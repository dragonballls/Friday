from __future__ import annotations

import os

import pytest

from core.gods_eye_bridge import GodsEyeBridge


def test_default_bridge_is_local() -> None:
    bridge = GodsEyeBridge.from_environment()
    assert bridge.base_url == "http://127.0.0.1:4173"


def test_location_url_validates_and_encodes_coordinates() -> None:
    bridge = GodsEyeBridge("http://localhost:4173")
    assert bridge.location_url(34.052235, -118.243683, zoom=10) == (
        "http://localhost:4173/?lat=34.052235&lon=-118.243683&zoom=10.00"
    )


def test_search_url_encodes_place() -> None:
    bridge = GodsEyeBridge("http://localhost:4173")
    assert bridge.search_url("Los Angeles, CA") == (
        "http://localhost:4173/?q=Los%20Angeles%2C%20CA"
    )


def test_capability_allowlist() -> None:
    bridge = GodsEyeBridge("http://127.0.0.1:4173")
    result = bridge.capability("show_world_context", layers=["aircraft"])
    assert result == {
        "capability": "show_world_context",
        "arguments": {"layers": ["aircraft"]},
    }

    with pytest.raises(ValueError):
        bridge.capability("arbitrary_network_request")


def test_non_local_url_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRIDAY_GODS_EYE_URL", "https://example.com")
    with pytest.raises(ValueError):
        GodsEyeBridge.from_environment()


def test_credentials_in_url_are_rejected() -> None:
    with pytest.raises(ValueError):
        GodsEyeBridge("http://user:pass@127.0.0.1:4173")
