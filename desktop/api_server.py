"""Local API server for Friday desktop - minimal mode exposes chat and self-coding."""

import argparse
import asyncio
import base64
import io
import json
import os
import platform
import re
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from quart import Quart, Response, jsonify, request, make_response
from quart_cors import cors

from agent.core import Agent
from core.automations import get_automation_engine
from core.briefing import BriefingEngine
from core.diary import get_diary
from core.logger import get_metrics
from core.memory import get_memory_manager
from core.proactive import CalendarMonitor, EmailMonitor, ProactiveMonitor, SystemMonitor
from core.registry import discover_plugins
from core.security import get_approval_registry
from core.vision import get_vision_engine

API_PREFIX = "/api/v1"
MINIMAL_MODE = os.getenv("FRIDAY_MINIMAL_MODE", "1").lower() not in {"0", "false", "no", "off"}

_async_client: httpx.AsyncClient | None = None


def get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Friday/1.0"})
    return _async_client


class EventBroadcaster:
    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue):
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def broadcast(self, event_type: str, data: dict):
        msg = json.dumps({"type": event_type, "data": data}, ensure_ascii=False) + "\n\n"
        async with self._lock:
            dead: list[asyncio.Queue] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(msg)
                except asyncio.QueueFull:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)


_broadcaster = EventBroadcaster()


def _load_dotenv():
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            if not os.environ.get(key):
                os.environ[key] = val


_load_dotenv()

_API_SECRET = os.environ.get("API_SECRET", "")


def require_auth(f):
    @wraps(f)
    async def wrapper(*args, **kwargs):
        if _API_SECRET:
            key = request.headers.get("X-API-Key", "")
            if key != _API_SECRET:
                return jsonify({"error": "Unauthorized"}), 401
        return await f(*args, **kwargs)

    return wrapper


_MAX_MESSAGE_LENGTH = 10_000
_VALID_LANGUAGES = {"english", "hinglish"}


def validate_chat_input(data: dict) -> str | None:
    msg = data.get("message", "")
    if not isinstance(msg, str):
        return "message must be a string"
    if not msg.strip():
        return "message cannot be empty"
    if len(msg) > _MAX_MESSAGE_LENGTH:
        return f"message exceeds {_MAX_MESSAGE_LENGTH} characters"
    return None


def validate_output_path(path: str) -> str | None:
    if ".." in path or path.startswith("~"):
        return "invalid path: directory traversal not allowed"
    return None


app = Quart(__name__)
app = cors(
    app,
    allow_origin={"http://localhost:5173", "http://127.0.0.1:5173", "https://dragonballls.github.io"},
    allow_methods={"GET", "POST", "PUT", "DELETE", "OPTIONS"},
    allow_headers={"Content-Type", "X-API-Key"},
    allow_credentials=True,
)

discover_plugins()

_agents: dict[str, Agent] = {}
_proactive: ProactiveMonitor | None = None
_diary = get_diary()


def get_proactive() -> ProactiveMonitor:
    global _proactive
    if _proactive is None:
        _proactive = ProactiveMonitor()
        _proactive.add_monitor(CalendarMonitor(interval=60.0))
        _proactive.add_monitor(EmailMonitor(interval=120.0))
        _proactive.add_monitor(SystemMonitor(interval=30.0))
        _proactive.start()
    return _proactive


def _get_agent(session_id: str, persona: str | None = None) -> Agent:
    if session_id not in _agents:
        _agents[session_id] = Agent(persona=persona)
    elif persona and _agents[session_id].persona != persona:
        _agents[session_id].persona = persona
        _agents[session_id].clear()
    return _agents[session_id]


@app.before_request
async def minimal_feature_gate():
    if not MINIMAL_MODE:
        return None
    if request.method == "OPTIONS":
        return None
    allowed = {
        f"{API_PREFIX}/chat",
        f"{API_PREFIX}/autopilot",
        f"{API_PREFIX}/health",
    }
    if request.path in allowed:
        return None
    if request.path.startswith(API_PREFIX):
        return jsonify({"error": "This Friday installation is in minimal mode; this feature is disabled."}), 404
    return None


@app.route(f"{API_PREFIX}/chat", methods=["POST"])
@require_auth
async def chat():
    data = await request.get_json() or {}
    err = validate_chat_input(data)
    if err:
        return jsonify({"error": err}), 422
    user_input = data.get("message", "")
    session_id = data.get("session_id", "default")
    persona = data.get("persona", "jarvis")
    agent = _get_agent(session_id, persona=persona)

    async def generate():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def _run():
            last_text = ""
            try:
                for event in agent.run(user_input):
                    last_text = event.get("content", last_text)
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "done", "content": f"Error: {e}", "final": True})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        executor.submit(_run)
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except TimeoutError:
            yield json.dumps({"type": "done", "content": "Request timed out", "final": True}) + "\n"
        finally:
            executor.shutdown(wait=False)

    response = await make_response(generate())
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.timeout = None
    return response


@app.route(f"{API_PREFIX}/autopilot", methods=["POST"])
@require_auth
async def autopilot():
    data = await request.get_json() or {}
    goal = data.get("goal", "")
    if not goal:
        return jsonify({"error": "goal is required"}), 422
    session_id = data.get("session_id", "default")
    workspace = data.get("workspace") or os.getenv("FRIDAY_WORKSPACE")
    if workspace:
        err = validate_output_path(workspace)
        if err:
            return jsonify({"error": err}), 422
    agent = _get_agent(session_id, persona="jarvis")

    async def generate():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

        def _run():
            try:
                for event in agent.run_autopilot(goal, workspace):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "done", "content": f"Autopilot error: {e}", "final": True})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        executor.submit(_run)
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=600)
                if event is None:
                    break
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except TimeoutError:
            yield json.dumps({"type": "done", "content": "Self-coding task timed out", "final": True}) + "\n"
        finally:
            executor.shutdown(wait=False)

    response = await make_response(generate())
    response.headers["Content-Type"] = "text/event-stream; charset=utf-8"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.timeout = None
    return response


@app.route(f"{API_PREFIX}/health")
async def health():
    return jsonify({"status": "ok", "sessions": len(_agents), "mode": "minimal" if MINIMAL_MODE else "full"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Friday local API server")
    parser.add_argument("--host", default=os.getenv("FRIDAY_API_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("FRIDAY_API_PORT", "8080")))
    args = parser.parse_args()
    app.run(host=args.host, port=args.port)
