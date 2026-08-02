class FakeLLMClient:
    def __init__(
        self,
        tool_call: dict | None = None,
        content: str = "",
    ):
        self.tool_call = tool_call
        self.content = content
        self._calls: list[dict] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        self._calls.append({"messages": messages, "tools": tools})

        if self.tool_call:
            return {"content": "", "tool_calls": [self.tool_call]}
        return {"content": self.content, "tool_calls": []}

    def get_last_call(self) -> dict:
        return self._calls[-1] if self._calls else {}
