import json

import httpx

from src.config import LLM_MAX_TOKENS, LLM_TEMPERATURE


class OllamaClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": LLM_TEMPERATURE,
                "num_predict": LLM_MAX_TOKENS,
            },
        }
        if tools:
            payload["tools"] = tools

        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()

        data = resp.json()
        msg = data.get("message", {})

        result = {"content": msg.get("content", ""), "tool_calls": []}
        if msg.get("tool_calls"):
            result["tool_calls"] = [
                {
                    "id": f"call_{i}",
                    "name": tc["function"]["name"],
                    "arguments": tc["function"]["arguments"]
                    if isinstance(tc["function"]["arguments"], dict)
                    else json.loads(tc["function"]["arguments"]),
                }
                for i, tc in enumerate(msg["tool_calls"])
            ]
        return result
