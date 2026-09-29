class FakeLLMClient:
    """Substituto determinístico de um LLM, usado nos testes e em LLM_PROVIDER=fake.

    `tool_call` aceita um único tool_call ou uma **lista** — uma entrada por
    rodada do loop de ferramentas. Quando a lista acaba (ou quando `tools=None`),
    o cliente responde com `content`, como faria um modelo real.
    """

    def __init__(self, tool_call: dict | list[dict] | None = None, content: str = ""):
        if tool_call is None:
            self._tool_calls: list[dict] = []
        elif isinstance(tool_call, list):
            self._tool_calls = tool_call
        else:
            self._tool_calls = [tool_call]
        self.content = content
        self._rodada = 0
        self._calls: list[dict] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        self._calls.append({"messages": messages, "tools": tools})

        # Sem `tools` o provedor nunca devolve tool_calls.
        if tools and self._rodada < len(self._tool_calls):
            chamada = dict(self._tool_calls[self._rodada])
            # Id único por rodada: ids repetidos corrompem o histórico de mensagens.
            chamada["id"] = f"call_{self._rodada}"
            self._rodada += 1
            return {"content": "", "tool_calls": [chamada]}
        return {"content": self.content, "tool_calls": []}

    def get_last_call(self) -> dict:
        return self._calls[-1] if self._calls else {}
