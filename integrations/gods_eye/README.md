# God's Eye integration

Friday treats God's Eye View as an optional, isolated spatial capability rather than merging its Node/Cesium dependency tree into the Python application.

## Design goals

- Keep Friday running if God's Eye is unavailable.
- Keep God's Eye's Node/Vite/Cesium runtime isolated.
- Prefer keyless/public capabilities.
- Never place provider secrets in browser-visible Friday configuration.
- Preserve God's Eye's third-party data-source attribution and provider terms.
- Expose a small capability contract so Friday can navigate, inspect, and receive spatial context.

## Capability contract

The bridge is intentionally transport-agnostic. A future adapter can use HTTP, WebSocket, or another local IPC mechanism without changing Friday's assistant layer.

Supported intents:

- `navigate_to`
- `show_route`
- `show_world_context`
- `inspect_selected_object`
- `track_object`
- `set_view`
- `get_current_view_context`
- `set_layers`

## Safety boundary

The bridge only describes requested spatial operations. It does not grant arbitrary shell execution, arbitrary URL fetching, credential access, or filesystem access to God's Eye.
