from integrations.gods_eye.adapter import GodsEyeAdapter


def test_adapter_builds_valid_request():
    request = GodsEyeAdapter().request("navigate_to", {"query": "Los Angeles"}, "req-2")
    assert request.capability == "navigate_to"
    assert request.arguments["query"] == "Los Angeles"


def test_adapter_normalizes_spatial_context():
    context = GodsEyeAdapter().context_from_event(
        {
            "latitude": 34.0522,
            "longitude": -118.2437,
            "active_layers": ["aircraft", "earthquakes"],
            "selected_object": {"kind": "aircraft", "id": "example"},
        }
    )
    assert context.latitude == 34.0522
    assert context.longitude == -118.2437
    assert context.active_layers == ("aircraft", "earthquakes")
    assert context.selected_object["kind"] == "aircraft"


def test_adapter_rejects_non_object_event():
    try:
        GodsEyeAdapter().context_from_event([])  # type: ignore[arg-type]
    except TypeError as exc:
        assert "must be an object" in str(exc)
    else:
        raise AssertionError("Invalid event was accepted")
