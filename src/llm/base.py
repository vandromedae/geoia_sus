from typing import Protocol


class LLMClient(Protocol):
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict: ...
