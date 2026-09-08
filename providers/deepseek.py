import os

from providers.base import BaseProvider
from providers.registry import register_provider


class DeepSeekProvider(BaseProvider):

    @property
    def name(self) -> str:
        return "deepseek"

    def __init__(self, config: dict):
        super().__init__(config)

        from openai import OpenAI

        api_key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or config.get("api_key")
        )

        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not configured."
            )

        self._client = OpenAI(
            api_key=api_key,
            base_url=config.get(
                "base_url",
                "https://api.deepseek.com",
            ),
        )

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ):

        model = self.config.get(
            "model",
            "deepseek-v4-flash",
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
            "max_tokens": max_tokens,
        }

        # Keep simple conversations fast.
        # Thinking can be enabled later for difficult tasks.
        if self.config.get("thinking", False):
            kwargs["extra_body"] = {
                "thinking": {
                    "type": "enabled"
                }
            }

        if tools:
            kwargs["tools"] = tools

        stream = self._client.chat.completions.create(
            **kwargs
        )

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
                            current["function"]["name"] = (
                                call.function.name
                            )

                        if call.function.arguments:
                            current["function"]["arguments"] += (
                                call.function.arguments
                            )

        yield {
            "type": "done",
            "content": full_text,
            "tool_calls": (
                list(tool_calls.values())
                if tool_calls
                else None
            ),
        }


register_provider("deepseek", DeepSeekProvider)
