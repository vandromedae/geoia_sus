import json

from src.llm.tools import (
    ALL_TOOLS,
    TOOL_BUSCAR_SETORES_MUNICIPIO,
    TOOL_BUSCAR_SETORES_PROXIMOS,
    TOOL_COMPARAR_MUNICIPIOS,
    TOOL_RANKING_MUNICIPIOS,
)


class TestToolDefinitions:
    def test_all_tools_count(self):
        assert len(ALL_TOOLS) == 4

    def test_tool_names(self):
        names = [t["function"]["name"] for t in ALL_TOOLS]
        assert "buscar_setores_proximos" in names
        assert "ranking_municipios" in names
        assert "comparar_municipios" in names
        assert "buscar_setores_municipio" in names

    def test_tool_structure(self):
        for tool in ALL_TOOLS:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]


class TestBuscarSetoresProximos:
    def test_required_params(self):
        params = TOOL_BUSCAR_SETORES_PROXIMOS["function"]["parameters"]
        assert "municipio" in params["properties"]
        assert "required" in params
        assert "municipio" in params["required"]

    def test_optional_params(self):
        params = TOOL_BUSCAR_SETORES_PROXIMOS["function"]["parameters"]
        assert "raio_km" in params["properties"]
        assert "limite_e2sfca" in params["properties"]
        assert "limite" in params["properties"]

    def test_description_mentions_proximity(self):
        desc = TOOL_BUSCAR_SETORES_PROXIMOS["function"]["description"]
        assert "próxim" in desc.lower() or "raio" in desc.lower()


class TestRankingMunicipios:
    def test_indicador_enum(self):
        params = TOOL_RANKING_MUNICIPIOS["function"]["parameters"]
        indicador = params["properties"]["indicador"]
        assert "enum" in indicador
        assert "medicos_por_1k" in indicador["enum"]

    def test_ordem_enum(self):
        params = TOOL_RANKING_MUNICIPIOS["function"]["parameters"]
        ordem = params["properties"]["ordem"]
        assert "enum" in ordem
        assert set(ordem["enum"]) == {"asc", "desc"}


class TestCompararMunicipios:
    def test_municipios_is_array(self):
        params = TOOL_COMPARAR_MUNICIPIOS["function"]["parameters"]
        municipios = params["properties"]["municipios"]
        assert municipios["type"] == "array"
        assert municipios["items"]["type"] == "string"

    def test_municipios_required(self):
        params = TOOL_COMPARAR_MUNICIPIOS["function"]["parameters"]
        assert "required" in params
        assert "municipios" in params["required"]


class TestBuscarSetoresMunicipio:
    def test_municipio_required(self):
        params = TOOL_BUSCAR_SETORES_MUNICIPIO["function"]["parameters"]
        assert "required" in params
        assert "municipio" in params["required"]

    def test_categoria_optional(self):
        params = TOOL_BUSCAR_SETORES_MUNICIPIO["function"]["parameters"]
        assert "categoria" in params["properties"]


class TestToolSerialization:
    def test_tools_are_json_serializable(self):
        serialized = json.dumps(ALL_TOOLS)
        deserialized = json.loads(serialized)
        assert len(deserialized) == 4
