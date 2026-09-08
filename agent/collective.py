from __future__ import annotations

import concurrent.futures
from typing import Any, Callable


# Providers that are currently confirmed in Friday's cloud pool.
DEFAULT_COLLECTIVE_PROVIDERS = (
    "openrouter",
    "groq",
    "gemini",
    "deepseek",
)


def should_use_collective(
    messages: list[dict],
    tools: list[dict] | None = None,
) -> bool:
    """
    Decide whether a request is complex enough to benefit from
    multiple independent cloud-model opinions.

    Normal/simple requests remain single-model for speed.
    """
    text = " ".join(
        str(m.get("content", ""))
        for m in messages
        if isinstance(m, dict)
    ).lower()

    complexity_markers = (
        "analyze",
        "analyse",
        "compare",
        "debug",
        "debugging",
        "architect",
        "architecture",
        "design",
        "implement",
        "implementation",
        "refactor",
        "review",
        "research",
        "investigate",
        "deep dive",
        "step by step",
        "multiple approaches",
        "best approach",
        "why is this failing",
        "find the bug",
        "complex",
    )

    long_request = len(text) >= 900
    has_tools = bool(tools)

    marker_hit = any(marker in text for marker in complexity_markers)

    return marker_hit or long_request or (has_tools and len(text) >= 500)


def select_collective_providers(
    available: list[str],
    max_providers: int = 3,
) -> list[str]:
    """
    Select distinct cloud providers for parallel reasoning.

    OpenRouter remains the primary provider. The other providers
    provide independent perspectives rather than sequential fallback.
    """
    preferred = [
        "openrouter",
        "groq",
        "gemini",
        "deepseek",
    ]

    result: list[str] = []

    for provider in preferred:
        if provider in available and provider not in result:
            result.append(provider)

        if len(result) >= max_providers:
            break

    return result


def run_collective(
    messages: list[dict],
    providers: list[str],
    call_provider: Callable[[str, list[dict]], Any],
) -> list[dict[str, Any]]:
    """
    Run selected providers concurrently.

    Each provider receives the same original request independently.
    A failure from one provider does not cancel the others.
    """
    results: list[dict[str, Any]] = []

    def run_one(provider: str) -> dict[str, Any]:
        try:
            result = call_provider(provider, messages)

            # Support Friday providers that return streaming generators.
            if hasattr(result, "__iter__") and not isinstance(
                result, (str, bytes, dict, list)
            ):
                events = list(result)

                content_parts: list[str] = []
                tool_calls = None

                for event in events:
                    if not isinstance(event, dict):
                        continue

                    if event.get("type") == "tokens":
                        content_parts.append(
                            str(event.get("content", ""))
                        )

                    if event.get("type") == "done":
                        if event.get("content"):
                            content_parts = [
                                str(event["content"])
                            ]
                        tool_calls = event.get("tool_calls")

                return {
                    "provider": provider,
                    "ok": True,
                    "content": "".join(content_parts),
                    "tool_calls": tool_calls,
                }

            if isinstance(result, dict):
                return {
                    "provider": provider,
                    "ok": True,
                    "content": str(result.get("content", "")),
                    "tool_calls": result.get("tool_calls"),
                }

            return {
                "provider": provider,
                "ok": True,
                "content": str(result),
                "tool_calls": None,
            }

        except Exception as exc:
            return {
                "provider": provider,
                "ok": False,
                "content": "",
                "tool_calls": None,
                "error": str(exc),
            }

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, len(providers))
    ) as executor:
        futures = [
            executor.submit(run_one, provider)
            for provider in providers
        ]

        for future in futures:
            results.append(future.result())

    return results


def build_synthesis_prompt(
    original_messages: list[dict],
    results: list[dict[str, Any]],
) -> list[dict]:
    """
    Prepare the independent answers for a final synthesis model.
    """

    original_text = "\n".join(
        str(message.get("content", ""))
        for message in original_messages
        if isinstance(message, dict)
    )

    evidence: list[str] = []

    for result in results:
        if not result.get("ok"):
            continue

        provider = result.get("provider", "unknown")
        content = result.get("content", "")

        evidence.append(
            f"=== {provider.upper()} INDEPENDENT ANALYSIS ===\n"
            f"{content}"
        )

    combined = "\n\n".join(evidence)

    synthesis = (
        "You are Friday's synthesis/judge model.\n\n"
        "Combine the independent cloud-model analyses below into one "
        "accurate answer.\n\n"
        "Rules:\n"
        "1. Do not blindly trust a majority vote.\n"
        "2. Identify contradictions between models.\n"
        "3. Prefer technically supported reasoning.\n"
        "4. Preserve useful details from different approaches.\n"
        "5. Do not mention internal provider mechanics unless relevant.\n"
        "6. Give one clear final answer.\n\n"
        f"ORIGINAL USER REQUEST:\n{original_text}\n\n"
        f"INDEPENDENT ANALYSES:\n{combined}"
    )

    return [
        {
            "role": "system",
            "content": synthesis,
        },
        {
            "role": "user",
            "content": "Produce the final synthesized answer.",
        },
    ]
