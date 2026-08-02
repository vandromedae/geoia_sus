import pytest

from src.llm.fake_client import FakeLLMClient
from src.llm.tools import ALL_TOOLS


class TestFakeLLMClient:
    def test_returns_content(self):
        client = FakeLLMClient(content="Olá mundo")
        result = client.chat(messages=[{"role": "user", "content": "Oi"}])
        assert result["content"] == "Olá mundo"
        assert result["tool_calls"] == []

    def test_returns_tool_call(self):
        tool_call = {
            "id": "call_0",
            "name": "ranking_municipios",
            "arguments": {"indicador": "medicos_por_1k"},
        }
        client = FakeLLMClient(tool_call=tool_call)
        result = client.chat(
            messages=[{"role": "user", "content": "ranking"}],
            tools=ALL_TOOLS,
        )
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "ranking_municipios"
        assert result["tool_calls"][0]["arguments"]["indicador"] == "medicos_por_1k"

    def test_records_calls(self):
        client = FakeLLMClient(content="ok")
        client.chat(messages=[{"role": "user", "content": "pergunta 1"}], tools=ALL_TOOLS)
        client.chat(messages=[{"role": "user", "content": "pergunta 2"}])

        assert len(client._calls) == 2
        assert client._calls[0]["messages"][0]["content"] == "pergunta 1"
        assert client._calls[1]["messages"][0]["content"] == "pergunta 2"

    def test_get_last_call(self):
        client = FakeLLMClient(content="ok")
        assert client.get_last_call() == {}

        client.chat(messages=[{"role": "user", "content": "teste"}])
        last = client.get_last_call()
        assert last["messages"][0]["content"] == "teste"


class TestOrchestratorWithFakeLLM:
    @pytest.mark.asyncio
    async def test_direct_answer(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(content="São Paulo tem 12 milhões de habitantes.")
        result = await processar_pergunta("Qual a população de SP?", db=db_session, llm=llm)
        assert "resposta" in result.model_dump()
        assert result.tool_chamada is None

    @pytest.mark.asyncio
    async def test_tool_call_ranking(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={
                "id": "call_0",
                "name": "ranking_municipios",
                "arguments": {"indicador": "medicos_por_1k", "ordem": "asc", "limite": 5},
            },
            content="Aqui está o ranking dos municípios com menos médicos por habitante.",
        )
        result = await processar_pergunta(
            "Quais municípios têm menos médicos?", db=db_session, llm=llm
        )
        assert result.tool_chamada == "ranking_municipios"
        assert result.dados is not None

        last = llm.get_last_call()
        msgs = last["messages"]
        assistant = [m for m in msgs if m["role"] == "assistant"][0]
        tool = [m for m in msgs if m["role"] == "tool"][0]
        assert assistant["tool_calls"][0]["id"] == "call_0"
        assert tool["tool_call_id"] == "call_0"

    @pytest.mark.asyncio
    async def test_tool_call_comparar(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={
                "id": "call_0",
                "name": "comparar_municipios",
                "arguments": {"municipios": ["Adamantina", "Adolfo"]},
            },
            content="Comparação entre Adamantina e Adolfo.",
        )
        result = await processar_pergunta("Compare Adamantina e Adolfo", db=db_session, llm=llm)
        assert result.tool_chamada == "comparar_municipios"
        assert isinstance(result.dados, list)

    @pytest.mark.asyncio
    async def test_tool_call_buscar_setores(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={
                "id": "call_0",
                "name": "buscar_setores_municipio",
                "arguments": {"municipio": "Adamantina"},
            },
            content="Setores de Adamantina.",
        )
        result = await processar_pergunta("Mostre os setores de Adamantina", db=db_session, llm=llm)
        assert result.tool_chamada == "buscar_setores_municipio"
        assert isinstance(result.dados, dict)
        assert result.dados["total_setores"] == 98
        assert len(result.dados["setores"]) == 98
