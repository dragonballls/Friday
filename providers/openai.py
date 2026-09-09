import os
from collections.abc import Generator
from typing import Any

from providers.base import BaseProvider
from providers.registry import register_provider


class OpenAIProvider(BaseProvider):
    @property
    def name(self) -> str:
        return "openai"

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        from openai import OpenAI

        api_key = os.environ.get("OPENAI_API_KEY") or config.get("api_key")

        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured.")

        self._client = OpenAI(
            api_key=api_key,
            max_retries=0,
            base_url=config.get(
                "base_url",
                "https://api.openai.com/v1",
            ),
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> Generator[dict, None, None]:

        model = self.config.get(
            "model",
            "gpt-5.6-luna",
        )

        temperature = self.config.get(
            "temperature",
            0.7,
        )

        max_tokens = self.config.get(
            "max_tokens",
            2048,
        )

        kwargs = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = tools

        stream = self._client.chat.completions.create(**kwargs)

        full_text = ""
        tool_calls = {}

        for chunk in stream:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                full_text += delta.content

                yield {
                    "type": "tokens",
                    "content": delta.content,
                }

            if delta.tool_calls:
                for call in delta.tool_calls:
                    index = call.index

                    if index not in tool_calls:
                        tool_calls[index] = {
                            "id": "",
                            "type": "function",
                            "function": {
                                "name": "",
                                "arguments": "",
                            },
                        }

                    current = tool_calls[index]

                    if call.id:
                        current["id"] = call.id

                    if call.function:
                        if call.function.name:
                            current["function"]["name"] = call.function.name

                        if call.function.arguments:
                            current["function"]["arguments"] += call.function.arguments

        normalized_tools = list(tool_calls.values()) if tool_calls else None

        yield {
            "type": "done",
            "content": full_text,
            "tool_calls": normalized_tools,
        }


register_provider("openai", OpenAIProvider)
