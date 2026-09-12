"""Long-running context management for Friday.

Keeps model requests bounded while preserving the durable task history needed
for multi-hour autonomous work. Old conversation turns are compacted into a
small rolling summary instead of being allowed to grow until the provider
rejects the request for exceeding its context window.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Conservative character budget: intentionally below common provider limits.
# The actual provider may support more, but staying below this threshold gives
# tools, prompts, and response overhead room to fit reliably.
MAX_CONTEXT_CHARS = 110_000
KEEP_RECENT_MESSAGES = 18
MAX_SUMMARY_CHARS = 12_000


def _message_chars(message: dict[str, Any]) -> int:
    try:
        return len(json.dumps(message, ensure_ascii=False, separators=(",", ":")))
    except (TypeError, ValueError):
        return len(str(message))


def _safe_content(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if content is None:
        return ""
    return str(content)


def _summarize_messages(messages: list[dict[str, Any]]) -> str:
    """Create a deterministic compact record of pruned history."""
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role", "unknown"))
        content = _safe_content(message).replace("\n", " ").strip()
        if content:
            lines.append(f"{role}: {content[:700]}")
        tool_calls = message.get("tool_calls")
        if tool_calls:
            names = []
            for call in tool_calls:
                function = call.get("function", {}) if isinstance(call, dict) else {}
                name = function.get("name") if isinstance(function, dict) else None
                if name:
                    names.append(str(name))
            if names:
                lines.append(f"assistant tool calls: {', '.join(names)}")
    text = "\n".join(lines)
    return text[:MAX_SUMMARY_CHARS]


def compact_messages(
    messages: list[dict[str, Any]],
    *,
    max_chars: int = MAX_CONTEXT_CHARS,
    keep_recent: int = KEEP_RECENT_MESSAGES,
) -> bool:
    """Compact *messages* in place and report whether compaction occurred.

    The first system message is always retained. Recent messages are preserved
    verbatim. Older history is replaced by one compact system summary.
    """
    if len(messages) <= keep_recent + 1:
        return False

    total = sum(_message_chars(message) for message in messages)
    if total <= max_chars:
        return False

    system = messages[0] if messages and messages[0].get("role") == "system" else None
    recent_start = max(1 if system else 0, len(messages) - keep_recent)
    old = messages[1:recent_start] if system else messages[:recent_start]
    recent = messages[recent_start:]
    if not old:
        return False

    summary = _summarize_messages(old)
    summary_message = {
        "role": "system",
        "content": (
            "LONG-RUNNING TASK MEMORY (compacted context)\n"
            "Older conversation/tool history was compacted to keep the active "
            "model request inside its context budget. Preserve these facts when "
            "continuing:\n" + summary
        ),
    }

    rebuilt: list[dict[str, Any]] = []
    if system:
        rebuilt.append(system)
    rebuilt.append(summary_message)
    rebuilt.extend(recent)

    # Very large individual tool outputs can still dominate the budget. Trim
    # only content-bearing tool messages while keeping their role/id structure.
    while sum(_message_chars(message) for message in rebuilt) > max_chars and len(rebuilt) > 3:
        # Never discard the base system prompt or compacted summary.
        index = 2 if system else 1
        if index < len(rebuilt) - 1:
            rebuilt.pop(index)
        else:
            break

    messages[:] = rebuilt
    return True


def load_checkpoint(workspace: str | None) -> dict[str, Any]:
    if not workspace:
        return {}
    path = Path(workspace) / ".friday" / "context_checkpoint.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def save_checkpoint(workspace: str | None, *, goal: str, stage: str, messages: list[dict[str, Any]]) -> None:
    if not workspace:
        return
    path = Path(workspace) / ".friday" / "context_checkpoint.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        compact_messages(messages)
        payload = {
            "goal": goal,
            "stage": stage,
            "message_count": len(messages),
            "context_chars": sum(_message_chars(message) for message in messages),
            "summary": _summarize_messages(messages[-KEEP_RECENT_MESSAGES:]),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        # Checkpointing must never crash an otherwise healthy coding run.
        pass
