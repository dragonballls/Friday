"""Persistent, user-controlled preferences for personal assistant behavior."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


PROFILE_PATH = Path(__file__).resolve().parent.parent / "memory_store" / "assistant_profile.json"
DEFAULT_PROFILE: dict[str, Any] = {
    "main_prompt": "",
    "learned_guidance": [],
    "response_style": "concise",
    "proactive_updates": True,
    "default_mode": "assistant",
    "focus_topics": [],
    "notes": "",
}


def _load() -> dict[str, Any]:
    try:
        data = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        return {**DEFAULT_PROFILE, **data} if isinstance(data, dict) else dict(DEFAULT_PROFILE)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return dict(DEFAULT_PROFILE)


def get_profile() -> dict[str, Any]:
    return _load()


def update_profile(changes: dict[str, Any]) -> dict[str, Any]:
    profile = _load()
    for key in DEFAULT_PROFILE:
        if key in changes:
            value = changes[key]
            if key == "learned_guidance":
                if not isinstance(value, list):
                    continue
                value = [str(item).strip()[:500] for item in value if str(item).strip()][:50]
            elif key == "main_prompt":
                value = str(value)[:12000]
            profile[key] = value
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix="assistant-profile-", suffix=".tmp", dir=PROFILE_PATH.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(profile, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, PROFILE_PATH)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise
    return profile
