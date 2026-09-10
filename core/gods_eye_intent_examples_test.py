from core.gods_eye_intent import classify_spatial_request


def test_common_spatial_requests_route_to_gods_eye():
    assert classify_spatial_request("Friday, show me the route to the museum").capability == "show_route"
    assert classify_spatial_request("what's around this area?").capability == "show_world_context"
    assert classify_spatial_request("what am I looking at?").capability == "inspect_selected_object"
    assert classify_spatial_request("show satellites").capability == "set_layers"


def test_non_spatial_request_is_not_routed():
    assert classify_spatial_request("write a short note about my homework") is None
