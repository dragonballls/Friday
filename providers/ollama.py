import time
from collections.abc import Generator
from typing import Any

from providers.base import BaseProvider
from providers.registry import register_provider


class OllamaProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "ollama"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        import ollama

        self._base_url = str(
            config.get(
                "base_url",
                "http://localhost:11434",
            )
        )

        self._timeout = float(
            config.get(
                "timeout",
                120,
            )
        )

        self._client = ollama.Client(
            host=self._base_url,
            timeout=self._timeout,
        )

    @staticmethod
    def _value(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(key, default)

        return getattr(obj, key, default)

    @classmethod
    def _function_value(
        cls,
        function: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        return cls._value(function, key, default)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[dict, None, None]:
        model = self.config.get(
            "model",
            "qwen2.5:3b",
        )

        temperature = self.config.get(
            "temperature",
            0.7,
        )

        max_tokens = self.config.get(
            "max_tokens",
            2048,
        )

        buffer: list[str] = []
        content_parts: list[str] = []
        tool_calls = None
        last_flush = time.monotonic()

        try:
            stream = self._client.chat(
                model=model,
                messages=messages,
                tools=tools,
                stream=True,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )

            stream_started = time.monotonic()

            for chunk in stream:
                if time.monotonic() - stream_started > self._timeout:
                    raise TimeoutError(
                        f"Ollama stream exceeded timeout of {self._timeout:.1f}s"
                    )

                stream_started = time.monotonic()

                message = self._value(
                    chunk,
                    "message",
                    {},
                )

                content = self._value(
                    message,
                    "content",
                    "",
                )

                if content:
                    buffer.append(str(content))
                    content_parts.append(str(content))

                    now = time.monotonic()

                    if now - last_flush >= 0.05 or len(buffer) >= 5:
                        text = "".join(buffer)
                        buffer.clear()
                        last_flush = now

                        yield {
                            "type": "tokens",
                            "content": text,
                        }

                raw_tool_calls = self._value(
                    message,
                    "tool_calls",
                    None,
                )

                if raw_tool_calls:
                    normalized = []

                    for tc in raw_tool_calls:
                        function = self._value(
                            tc,
                            "function",
                            {},
                        )

                        name = self._function_value(
                            function,
                            "name",
                            "?",
                        )

                        arguments = self._function_value(
                            function,
                            "arguments",
                            {},
                        )

                        tc_id = self._value(
                            tc,
                            "id",
                            "",
                        )

                        normalized.append(
                            {
                                "id": str(tc_id or ""),
                                "type": "function",
                                "function": {
                                    "name": str(name or "?"),
                                    "arguments": arguments,
                                },
                            }
                        )

                    tool_calls = normalized

            if buffer:
                yield {
                    "type": "tokens",
                    "content": "".join(buffer),
                }

            yield {
                "type": "done",
                "content": "".join(content_parts),
                "tool_calls": tool_calls,
            }

        except Exception as exc:
            error_text = (
                f"Ollama request failed "
                f"(model={model}, "
                f"url={self._base_url}): "
                f"{type(exc).__name__}: {exc}"
            )

            yield {
                "type": "error",
                "error": error_text,
                "provider": "ollama",
                "model": model,
            }

            yield {
                "type": "done",
                "content": "".join(content_parts),
                "tool_calls": tool_calls,
                "error": error_text,
            }


register_provider("ollama", OllamaProvider)
