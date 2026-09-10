from __future__ import annotations

from core import registry


def test_gods_eye_plugins_are_auto_discovered() -> None:
    registry.discover_plugins()
    tools = registry.get_tool_map()
    assert "gods_eye_navigate" in tools
    assert "gods_eye_capability" in tools
    assert "gods_eye_health" in tools


def test_gods_eye_plugins_have_definitions() -> None:
    registry.discover_plugins()
    names = {
        definition["function"]["name"]
        for definition in registry.get_tool_definitions()
        if definition.get("type") == "function"
    }
    assert {"gods_eye_navigate", "gods_eye_capability", "gods_eye_health"} <= names
