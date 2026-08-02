import json

from groq import Groq

from src.config import LLM_MAX_TOKENS, LLM_TEMPERATURE


class GroqClient:
    def __init__(self, api_key: str, model: str):
        self.client = Groq(api_key=api_key)
        self.model = model

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": LLM_TEMPERATURE,
            "max_tokens": LLM_MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = self.client.chat.completions.create(**kwargs)
        msg = response.choices[0].message

        result = {"content": msg.content or "", "tool_calls": []}
        if msg.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                }
                for tc in msg.tool_calls
            ]
        return result
