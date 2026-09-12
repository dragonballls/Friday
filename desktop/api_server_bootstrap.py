"""Packaged Friday API bootstrap.

Keeps the desktop API available even when optional startup services fail.
The Tauri WebView uses the tauri.localhost origin, so production CORS headers
are added here. The autonomous coder is started alongside the API process.
"""
from __future__ import annotations

import asyncio
import os
import threading

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


def _safe_background_start(name: str, target) -> None:
    try:
        target()
    except Exception as exc:
        logger = getattr(api_server, "warn", None)
        if callable(logger):
            logger(f"Optional startup service {name} skipped: {exc}")


def _start_autonomous_coder() -> None:
    if os.getenv("FRIDAY_AUTONOMOUS_CODING", "1").strip().lower() in {"0", "false", "no", "off"}:
        return
    try:
        from tools.autonomous_coder import main as autonomous_main
        thread = threading.Thread(target=autonomous_main, name="FridayAutonomousCoder", daemon=True)
        thread.start()
    except Exception as exc:
        logger = getattr(api_server, "warn", None)
        if callable(logger):
            logger(f"Autonomous coder startup skipped: {exc}")


def _start_optional_services() -> None:
    def _embeddings() -> None:
        from core.memory.embeddings import SentenceEngine
        SentenceEngine.start_background_load()

    def _hotkey() -> None:
        from core.hotkey import start_hotkey_listener
        start_hotkey_listener()

    _safe_background_start("embeddings", _embeddings)
    if os.environ.get("FRIDAY_HOTKEY", "1").strip().lower() not in {"0", "false", "no", "off"}:
        _safe_background_start("hotkey", _hotkey)


def _run_server() -> None:
    import hypercorn.asyncio
    from hypercorn.config import Config

    cfg = Config()
    args = api_server.parse_args()
    cfg.bind = [f"{args.host}:{args.port}"]
    cfg.keep_alive_timeout = 300
    cfg.body_timeout = 300

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # The API server is the critical service. Optional background services are
    # started only after the event loop is ready so they cannot block startup.
    for factory in (
        api_server._memory_consolidation_loop,
        api_server._proactive_loop,
        api_server._push_metrics,
        api_server._push_briefing,
        api_server._push_nightly_digest,
        api_server._push_automations,
        api_server._push_vision,
        api_server._push_system_info,
        api_server._push_memory,
        api_server._push_alerts,
        api_server._push_screen,
        api_server._push_clocks,
    ):
        try:
            loop.create_task(factory())
        except Exception as exc:
            logger = getattr(api_server, "warn", None)
            if callable(logger):
                logger(f"Optional async service {getattr(factory, '__name__', factory)} skipped: {exc}")

    threading.Thread(target=_start_optional_services, name="FridayOptionalStartup", daemon=True).start()
    loop.run_until_complete(hypercorn.asyncio.serve(api_server.app, cfg))


if __name__ == "__main__":
    _start_autonomous_coder()
    _run_server()
