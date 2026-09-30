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


class TestLoopDeFerramentas:
    @pytest.mark.asyncio
    async def test_varias_rodadas_executam_todas_as_ferramentas(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call=[
                {
                    "name": "comparar_municipios",
                    "arguments": {"municipios": ["Adamantina"]},
                },
                {"name": "ranking_municipios", "arguments": {"limite": 3}},
            ],
            content="Resposta final.",
        )
        result = await processar_pergunta("Compare e faça um ranking", db=db_session, llm=llm)

        assert result.tool_chamada == "comparar_municipios, ranking_municipios"
        assert result.resposta == "Resposta final."
        # 2 rodadas com ferramenta + 1 chamada final sem ferramentas.
        assert len(llm._calls) == 3

        tool_ids = [
            m["tool_call_id"] for m in llm.get_last_call()["messages"] if m["role"] == "tool"
        ]
        assert tool_ids == ["call_0", "call_1"]

    @pytest.mark.asyncio
    async def test_chamada_final_e_sem_ferramentas(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        # Duas rodadas de ferramenta esgotam o limite e forçam uma chamada final
        # SEM ferramentas — senão o modelo ficaria preso pedindo ferramenta para
        # sempre e a resposta nunca sairia.
        llm = FakeLLMClient(
            tool_call=[
                {"name": "ranking_municipios", "arguments": {"limite": 3}},
                {"name": "comparar_municipios", "arguments": {"municipios": ["Adamantina"]}},
            ],
            content="ok",
        )
        result = await processar_pergunta("Ranking e depois comparar", db=db_session, llm=llm)

        assert len(llm._calls) == 3
        assert llm.get_last_call()["tools"] is None
        assert result.resposta == "ok"

    @pytest.mark.asyncio
    async def test_nao_serializa_o_event_loop(self, db_session):
        import asyncio
        import time

        from src.llm.orchestrator import processar_pergunta

        class LLMLento(FakeLLMClient):
            def chat(self, messages, tools=None):
                time.sleep(0.4)
                return super().chat(messages, tools)

        tarefa = asyncio.create_task(
            processar_pergunta(
                "quantos médicos tem Campinas", db=db_session, llm=LLMLento(content="ok")
            )
        )

        # Se `processar_pergunta` rodasse bloqueante no event loop, este sleep
        # esperaria os 0,4 s do LLM antes de acordar.
        inicio = time.perf_counter()
        await asyncio.sleep(0.05)
        demorou = time.perf_counter() - inicio

        await tarefa
        assert demorou < 0.3, f"event loop ficou {demorou:.2f}s travado"

    @pytest.mark.asyncio
    async def test_limite_do_modelo_e_limitado_no_servidor(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={"name": "ranking_municipios", "arguments": {"limite": 10000}},
            content="ok",
        )
        result = await processar_pergunta("Ranking dos municípios", db=db_session, llm=llm)
        assert isinstance(result.dados, list)
        assert len(result.dados) <= 100

    @pytest.mark.asyncio
    async def test_erro_de_ferramenta_nao_vaza_como_dados(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={"name": "buscar_setores_proximos", "arguments": {}},
            content="Faltou o município.",
        )
        result = await processar_pergunta("Setores com acesso ruim no raio", db=db_session, llm=llm)
        assert result.dados is None
        assert result.resposta == "Faltou o município."


class TestRespostaDeFallback:
    @pytest.mark.asyncio
    async def test_resposta_em_branco_com_dados_de_setores(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={
                "name": "buscar_setores_municipio",
                "arguments": {"municipio": "Adamantina"},
            },
            content="   ",
        )
        result = await processar_pergunta("Mostre os setores de Adamantina", db=db_session, llm=llm)
        assert "98 setores" in result.resposta

    @pytest.mark.asyncio
    async def test_resposta_em_branco_sem_ferramenta(self, db_session):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(content="")
        result = await processar_pergunta("quantos médicos tem Campinas", db=db_session, llm=llm)
        assert result.resposta.strip() != ""


class TestResumirParaLLM:
    def test_lista_e_truncada_e_sem_coordenadas(self):
        from src.llm.serializacao import resumir_para_llm

        lista = [
            {"cd_setor": str(i), "latitude": -23.5, "longitude": -46.6, "v0001": i}
            for i in range(50)
        ]
        projecao = resumir_para_llm(lista)

        assert projecao["total_itens"] == 50
        assert len(projecao["itens"]) == 20
        assert "latitude" not in projecao["itens"][0]
        assert "longitude" not in projecao["itens"][0]
        assert projecao["itens"][0]["cd_setor"] == "0"

    def test_dict_de_setores_mantem_resumo_e_total(self):
        from src.llm.serializacao import resumir_para_llm

        dados = {
            "municipio": "Adamantina",
            "distrito": None,
            "categoria": None,
            "total_setores": 98,
            "resumo": {"media_e2sfca": 0.5},
            "setores": [
                {"cd_setor": "1", "latitude": -23.5, "longitude": -46.6},
                {"cd_setor": "2", "latitude": -23.6, "longitude": -46.7},
            ],
        }
        projecao = resumir_para_llm(dados)

        assert projecao["total_setores"] == 98
        assert projecao["resumo"] == {"media_e2sfca": 0.5}
        assert len(projecao["amostra_ordenada_do_pior_para_o_melhor_acesso"]) == 2
        assert "latitude" not in projecao["amostra_ordenada_do_pior_para_o_melhor_acesso"][0]

    def test_dict_de_erro_e_repassado_intacto(self):
        from src.llm.serializacao import resumir_para_llm

        erro = {"erro": "Parâmetro 'municipio' é obrigatório"}
        assert resumir_para_llm(erro) == erro


class TestClampLimite:
    @pytest.mark.parametrize(
        ("valor", "padrao", "esperado"),
        [
            (None, 50, 50),
            ("abc", 50, 50),
            (0, 50, 50),
            (-3, 50, 50),
            (10, 50, 10),
            (100, 50, 100),
            (10000, 10, 100),
            (75.0, 10, 75),
        ],
    )
    def test_clamp(self, valor, padrao, esperado):
        from src.llm.ferramentas import clamp_limite

        assert clamp_limite(valor, padrao) == esperado


class TestCalcularMapa:
    """`mapa_centro`/`mapa_zoom` existiam na API mas o frontend não os lia."""

    def test_centro_e_a_media_de_todos_os_pontos(self):
        from src.llm.serializacao import calcular_mapa

        dados = [
            {"latitude": 10.0, "longitude": 0.0},
            {"latitude": 20.0, "longitude": 10.0},
        ]
        centro, zoom = calcular_mapa(dados)

        assert centro == [15.0, 5.0]
        assert zoom > 0

    def test_nao_usa_o_primeiro_ponto(self):
        """O primeiro ponto era o pior acesso — o mapa saía num canto."""
        from src.llm.serializacao import calcular_mapa

        dados = [
            {"latitude": 0.0, "longitude": 0.0},
            {"latitude": 10.0, "longitude": 0.0},
            {"latitude": 20.0, "longitude": 0.0},
        ]
        centro, _ = calcular_mapa(dados)

        assert centro == [10.0, 0.0]

    def test_le_setores_de_dicionario(self):
        from src.llm.serializacao import calcular_mapa

        centro, _ = calcular_mapa({"setores": [{"lat": 4.0, "lon": 8.0}]})

        assert centro == [4.0, 8.0]

    def test_sem_pontos(self):
        from src.llm.serializacao import calcular_mapa

        assert calcular_mapa([]) == (None, 10)
        assert calcular_mapa([{"nm_mun": "Adamantina"}]) == (None, 10)
        assert calcular_mapa(None) == (None, 10)

    def test_coordenada_invalida_e_ignorada(self):
        from src.llm.serializacao import calcular_mapa

        centro, _ = calcular_mapa(
            [
                {"latitude": "x", "longitude": "y"},
                {"latitude": 2.0, "longitude": 3.0},
            ]
        )

        assert centro == [2.0, 3.0]

    def test_zoom_cobre_a_extensao(self):
        from src.llm.serializacao import zoom_para

        # Município inteiro (~1,2°) não pode ficar em zoom 11 (fixo, antigo).
        assert zoom_para(1.2) == 9
        # Ponto único / extensão nula.
        assert zoom_para(0) == 12
        # Fora da faixa útil do slippy map.
        assert zoom_para(100) == 4
        assert zoom_para(0.001) == 15


class TestCaminhoCompletoSemBanco:
    """Roteamento -> LLM -> ferramenta -> serialização, sem PostGIS no ar.

    `db=None` de propósito: se algum ponto da coreografia tocar o banco, quebra
    aqui. Os testes de integração (`db_session`) seguem cobrindo o SQL real;
    estes cobram o caminho do `/query` para `make test` rodar sem Docker.
    """

    @pytest.fixture
    def espacial_mocado(self, monkeypatch):
        from types import SimpleNamespace

        import src.llm.ferramentas as ferramentas
        from src.services.spatial import Resolucao

        monkeypatch.setattr(
            ferramentas,
            "resolver_municipio",
            lambda db, nome: Resolucao(nome="Adamantina", codigo="3500105"),
        )
        monkeypatch.setattr(
            ferramentas,
            "ranking_municipios_db",
            lambda db, **kw: [
                SimpleNamespace(
                    cod_mun_ibge="3500105",
                    nm_mun="Adamantina",
                    medicos_por_1k=1.2,
                    total_medicos=330,
                    total_cnes=20,
                    populacao=34687.0,
                    categoria_densidade="5. Ex",
                )
            ],
        )
        monkeypatch.setattr(
            ferramentas,
            "buscar_setores_proximos_db",
            lambda db, **kw: [
                SimpleNamespace(
                    cd_setor="350010505000127",
                    nm_mun="Adamantina",
                    nm_dist=None,
                    acessibilidade_e2sfca=0.0017,
                    categoria_acesso="4. Limitado (acesso baixo)",
                    dist_minima_metros=3339.0,
                    total_medicos_dentro=0,
                    v0001=120,
                    latitude=-21.6,
                    longitude=-51.0,
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_ranking_completa_o_caminho(self, espacial_mocado):
        import json

        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={"name": "ranking_municipios", "arguments": {"limite": 5}},
            content="Adamantina tem o menor valor.",
        )
        result = await processar_pergunta(
            "Ranking de municípios com menos médicos", db=None, llm=llm
        )

        assert result.tool_chamada == "ranking_municipios"
        assert result.dados[0]["nm_mun"] == "Adamantina"
        assert result.resposta == "Adamantina tem o menor valor."
        assert result.resposta_de_fallback is False
        # Ranking não tem coordenadas: não há o que enquadrar no mapa.
        assert result.mapa_centro is None

        ferramenta = [m for m in llm.get_last_call()["messages"] if m["role"] == "tool"][0]
        assert json.loads(ferramenta["content"])["total_itens"] == 1

    @pytest.mark.asyncio
    async def test_setores_alimentam_o_mapa_e_vao_sem_lat_lon_ao_prompt(self, espacial_mocado):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={
                "name": "buscar_setores_proximos",
                "arguments": {"municipio": "Adamantina", "raio_km": 5},
            },
            content="Setores próximos.",
        )
        result = await processar_pergunta(
            "Quais setores ficam a 5 km do centro de Adamantina?",
            db=None,
            llm=llm,
        )

        assert result.mapa_centro == [-21.6, -51.0]
        # Ponto único: extensão 0 -> zoom padrão do slippy map.
        assert result.mapa_zoom == 12

        ferramenta = [m for m in llm.get_last_call()["messages"] if m["role"] == "tool"][0]
        assert "latitude" not in ferramenta["content"]
        assert "350010505000127" in ferramenta["content"]

    @pytest.mark.asyncio
    async def test_erro_de_ferramenta_vira_texto_e_nao_dados(self):
        from src.llm.orchestrator import processar_pergunta

        # Sem `municipio` a ferramenta devolve `{"erro": ...}` sem tocar o banco.
        llm = FakeLLMClient(
            tool_call={"name": "buscar_setores_proximos", "arguments": {}},
            content="Faltou o município.",
        )
        result = await processar_pergunta("Setores próximos aqui perto", db=None, llm=llm)

        assert result.dados is None
        assert result.resposta == "Faltou o município."

    @pytest.mark.asyncio
    async def test_erro_de_ferramenta_com_resposta_em_branco_e_explicado(self):
        from src.llm.orchestrator import processar_pergunta

        llm = FakeLLMClient(
            tool_call={"name": "buscar_setores_proximos", "arguments": {}},
            content="   ",
        )
        result = await processar_pergunta("Setores próximos aqui perto", db=None, llm=llm)

        assert result.resposta_de_fallback is True
        assert "Parâmetro 'municipio' é obrigatório" in result.resposta

    @pytest.mark.asyncio
    async def test_fora_de_escopo_nem_chama_o_llm(self):
        from src.llm.orchestrator import processar_pergunta

        class LLMQueNaoDeveriaSerChamado:
            def chat(self, messages, tools=None):
                raise AssertionError("fora do escopo não deveria chegar no LLM")

        result = await processar_pergunta(
            "me conte uma piada sobre gatos",
            db=None,
            llm=LLMQueNaoDeveriaSerChamado(),
        )

        assert "fora do escopo" in result.resposta
        assert result.dados is None
        assert result.tool_chamada is None
