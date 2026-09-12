"""Packaged Friday API bootstrap.

The Tauri WebView uses the tauri.localhost origin, which is different from the
Vite development origins accepted by api_server.py. This wrapper adds the
production desktop CORS headers and starts the persistent autonomous coder in
the same sidecar process so it does not depend on a separate PowerShell task.
"""

from __future__ import annotations

import asyncio
import os
import threading
from datetime import UTC, date, datetime, timedelta

import api_server

_ALLOWED_TAURI_ORIGINS = {
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
}


@api_server.app.after_request
async def _desktop_cors(response):
    origin = api_server.request.headers.get("Origin", "")
    if origin in _ALLOWED_TAURI_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key"
    return response


def _start_autonomous_coder() -> None:
    if os.getenv("FRIDAY_AUTONOMOUS_CODING", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    try:
        from tools.autonomous_coder import main as autonomous_main

        thread = threading.Thread(target=autonomous_main, name="FridayAutonomousCoder", daemon=True)
        thread.start()
    except Exception as exc:
        api_server.warn(f"Autonomous coder startup skipped: {exc}") if hasattr(api_server, "warn") else None


def _run_server() -> None:
    from core.memory.embeddings import SentenceEngine

    SentenceEngine.start_background_load()

    if os.environ.get("FRIDAY_HOTKEY", "1") not in ("0", "false", "no"):
        from core.hotkey import start_hotkey_listener

        start_hotkey_listener()

    import hypercorn.asyncio
    from hypercorn.config import Config

    cfg = Config()
    args = api_server.parse_args()
    cfg.bind = [f"{args.host}:{args.port}"]
    cfg.keep_alive_timeout = 300
    cfg.body_timeout = 300
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(api_server._memory_consolidation_loop())
    loop.create_task(api_server._proactive_loop())
    loop.create_task(api_server._push_metrics())
    loop.create_task(api_server._push_briefing())
    loop.create_task(api_server._push_nightly_digest())
    loop.create_task(api_server._push_automations())
    loop.create_task(api_server._push_vision())
    loop.create_task(api_server._push_system_info())
    loop.create_task(api_server._push_memory())
    loop.create_task(api_server._push_alerts())
    loop.create_task(api_server._push_screen())
    loop.create_task(api_server._push_clocks())
    loop.run_until_complete(hypercorn.asyncio.serve(api_server.app, cfg))


if __name__ == "__main__":
    _start_autonomous_coder()
    _run_server()
