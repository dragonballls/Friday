from contract import build_request


def test_allowed_capability_is_accepted():
    request = build_request("navigate_to", {"query": "Los Angeles"}, "req-1")
    assert request.capability == "navigate_to"
    assert request.arguments["query"] == "Los Angeles"


def test_unknown_capability_is_rejected():
    try:
        build_request("arbitrary_shell", {})  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Unsupported God's Eye capability" in str(exc)
    else:
        raise AssertionError("Unknown capability was accepted")
