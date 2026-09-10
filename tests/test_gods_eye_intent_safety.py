from core.gods_eye_intent import classify_spatial_request


def test_generic_show_me_does_not_route_to_gods_eye():
    assert classify_spatial_request("show me the settings") is None


def test_generic_go_to_does_not_route_to_gods_eye():
    assert classify_spatial_request("go to the downloads folder") is None


def test_specific_location_request_routes_to_gods_eye():
    result = classify_spatial_request("show me this location")
    assert result is not None
    assert result.capability == "navigate_to"


def test_existing_spatial_capabilities_remain_routable():
    assert classify_spatial_request("show aircraft")
    assert classify_spatial_request("what's around this area")
    assert classify_spatial_request("track that")
