from pydantic import BaseModel


class MunicipioResponse(BaseModel):
    cod_mun_ibge: str
    nm_mun: str
    populacao: float | None
    area_km2: float | None
    num_setores: int | None
    total_medicos: int | None
    total_cnes: int | None
    medicos_por_1k: float | None
    categoria_densidade: str | None
    uf: str | None

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    pergunta: str


class QueryResponse(BaseModel):
    resposta: str
    dados: list[dict] | dict | None = None
    tool_chamada: str | None = None
    mapa_centro: list[float] | None = None  # [lat, lng]
    mapa_zoom: int = 10
    # True quando o texto veio de `resposta_de_fallback` (LLM não gerou
    # conteúdo). A rota `/query` não coloca essas respostas no cache.
    resposta_de_fallback: bool = False
