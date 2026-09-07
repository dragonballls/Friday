from __future__ import annotations

import json
import re
import time
from collections.abc import Generator
from typing import TYPE_CHECKING, Any

import httpx

from providers.base import BaseProvider
from providers.registry import register_provider

if TYPE_CHECKING:
    from openai import OpenAI


def _is_retryable_err(e: Exception) -> bool:
    msg = str(e).lower()
    if any(x in msg for x in ["deadline", "timeout", "timed out", "too many requests", "rate limit"]):
        return True
    # curl error 16 = HTTP/2 framing failure
    if "curl: (16)" in msg or "http2" in msg or "http/2" in msg:
        return True
    return False



def _parse_text_tool_calls(content: str) -> list[dict]:
    """Parse tool calls emitted as ordinary assistant text."""

    if not content:
        return []

    parsed_tool_calls = []

    # XML invoke format used by some OpenRouter free models.
    invoke_pattern = re.compile(
        r'<invoke\s+name\s*=\s*["\']([^"\']+)["\']\s*>(.*?)</invoke>',
        flags=re.DOTALL | re.IGNORECASE,
    )

    parameter_pattern = re.compile(
        r'<parameter\s+name\s*=\s*["\']([^"\']+)["\']\s*>\s*(.*?)\s*</parameter>',
        flags=re.DOTALL | re.IGNORECASE,
    )

    for match in invoke_pattern.finditer(content):
        name = match.group(1).strip()
        body = match.group(2)
        args = {}

        for parameter in parameter_pattern.finditer(body):
            key = parameter.group(1).strip()
            value = parameter.group(2).strip()
            args[key] = value

        if "file_path" in args and "path" not in args:
            args["path"] = args.pop("file_path")

        parsed_tool_calls.append(
            {
                "id": f"text-invoke-{len(parsed_tool_calls)}",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args),
                },
            }
        )

    # JSON tool-call format.
    if not parsed_tool_calls:
        json_pattern = re.compile(
            r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
            flags=re.DOTALL | re.IGNORECASE,
        )

        for match in json_pattern.finditer(content):
            try:
                obj = json.loads(match.group(1).strip())

                if not isinstance(obj, dict):
                    continue

                name = (
                    obj.get("name")
                    or obj.get("tool")
                    or obj.get("function", {}).get("name")
                )

                arguments = (
                    obj.get("arguments")
                    or obj.get("args")
                    or obj.get("function", {}).get("arguments")
                    or {}
                )

                if not name:
                    continue

                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except Exception:
                        arguments = {"value": arguments}

                parsed_tool_calls.append(
                    {
                        "id": f"text-json-{len(parsed_tool_calls)}",
                        "type": "function",
                        "function": {
                            "name": str(name),
                            "arguments": json.dumps(arguments),
                        },
                    }
                )
            except Exception:
                continue

    # Bracket tool-call format.
    if not parsed_tool_calls:
        bracket_pattern = re.compile(
            r"\[TOOL_CALL\]\s*(.*?)\s*\[/TOOL_CALL\]",
            flags=re.DOTALL | re.IGNORECASE,
        )

        for match in bracket_pattern.finditer(content):
            block = match.group(1)

            tool_match = re.search(
                r'(?:tool|name)\s*=>\s*["\']([^"\']+)["\']',
                block,
                flags=re.IGNORECASE,
            )

            if not tool_match:
                continue

            name = tool_match.group(1).strip()
            args = {}

            for arg_match in re.finditer(
                r'--([A-Za-z_][A-Za-z0-9_-]*)\s+["\']([^"\']*)["\']',
                block,
            ):
                args[arg_match.group(1)] = arg_match.group(2)

            if "file_path" in args and "path" not in args:
                args["path"] = args.pop("file_path")

            parsed_tool_calls.append(
                {
                    "id": f"text-bracket-{len(parsed_tool_calls)}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(args),
                    },
                }
            )

    return parsed_tool_calls

class OpenAICompatibleProvider(BaseProvider):
    @property
    def name(self) -> str:
        return self.config.get("provider_name", "openai")

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self._client = None

    def _get_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        from openai import OpenAI

        api_key = self.config.get("api_key", "") or ""
        base_url = self.config.get("base_url", "https://api.openai.com/v1")
        timeout = self.config.get("timeout", 30)
        http_client = httpx.Client(http2=False, timeout=httpx.Timeout(timeout))
        self._client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        return self._client

    def _stream(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int,
    ) -> Generator[dict, None, None]:
        kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
        )
        if tools:
            kwargs["tools"] = tools

        client = self._get_client()
        stream = client.chat.completions.create(**kwargs)

        buffer: list[str] = []
        last_flush = time.monotonic()
        content_parts: list[str] = []
        tool_calls_acc: dict[int, dict] = {}

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if not delta:
                continue

            if delta.content:
                buffer.append(delta.content)
                content_parts.append(delta.content)
                now = time.monotonic()
                if now - last_flush >= 0.05 or len(buffer) >= 5:
                    yield {"type": "tokens", "content": "".join(buffer)}
                    buffer.clear()
                    last_flush = now

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc.id or "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["function"]["name"] += tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments

        if buffer:
            yield {"type": "tokens", "content": "".join(buffer)}

        content = "".join(content_parts)
        tool_calls = (
            [v for _, v in sorted(tool_calls_acc.items())]
            if tool_calls_acc
            else None
        )

        if not tool_calls and content:
            parsed_tool_calls = _parse_text_tool_calls(content)

            if parsed_tool_calls:
                tool_calls = parsed_tool_calls

                content = re.sub(
                    r"<tool_call>.*?</tool_call>",
                    "",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                )

                content = re.sub(
                    r"\[TOOL_CALL\].*?\[/TOOL_CALL\]",
                    "",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                )

                content = re.sub(
                    r'<invoke\s+name\s*=\s*["\'][^"\']+["\']\s*>.*?</invoke>',
                    "",
                    content,
                    flags=re.DOTALL | re.IGNORECASE,
                ).strip()

        yield {
            "type": "done",
            "content": content,
            "tool_calls": tool_calls,
        }

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[dict, None, None]:
        model = self.config.get("model", "gpt-5.6-luna")
        fallback = self.config.get("fallback_model", "openai/gpt-4o-mini")
        temperature = self.config.get("temperature", 0.7)
        max_tokens = self.config.get("max_tokens", 4096)

        try:
            yield from self._stream(model, messages, tools, temperature, max_tokens)
        except Exception as e:
            err_msg = str(e)
            yield {
                "type": "error",
                "error": err_msg,
                "content": f"Error: {err_msg}",
                "final": True,
            }


register_provider("openai", OpenAICompatibleProvider)
register_provider("openrouter", OpenAICompatibleProvider)
register_provider("openai_compatible", OpenAICompatibleProvider)
