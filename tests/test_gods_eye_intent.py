from core.gods_eye_intent import classify_spatial_request


def test_route_request_maps_to_route_capability() -> None:
    intent = classify_spatial_request("Friday, walk me through the route to the location")
    assert intent is not None
    assert intent.capability == "show_route"


def test_context_request_maps_to_world_context() -> None:
    intent = classify_spatial_request("What's around this area?")
    assert intent is not None
    assert intent.capability == "show_world_context"


def test_layer_request_maps_to_layers() -> None:
    intent = classify_spatial_request("Show aircraft and satellites")
    assert intent is not None
    assert intent.capability == "set_layers"


def test_unknown_request_is_not_forced_into_gods_eye() -> None:
    assert classify_spatial_request("Tell me a joke") is None
