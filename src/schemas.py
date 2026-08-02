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


class SetorResponse(BaseModel):
    cd_setor: str
    nm_mun: str | None
    nm_dist: str | None
    area_km2: float | None
    v0001: float | None
    acessibilidade_e2sfca: float | None
    categoria_acesso: str | None
    dist_minima_metros: float | None
    total_medicos_dentro: int | None
    total_cnes_dentro: int | None

    model_config = {"from_attributes": True}


class CnesResponse(BaseModel):
    id: int
    cnes: str | None
    municipio: str | None
    nome_fantasia: str | None
    total_medicos: int | None
    latitude: float | None
    longitude: float | None

    model_config = {"from_attributes": True}


class QueryRequest(BaseModel):
    pergunta: str


class QueryResponse(BaseModel):
    resposta: str
    dados: list[dict] | dict | None = None
    tool_chamada: str | None = None
    mapa_centro: list[float] | None = None  # [lat, lng]
    mapa_zoom: int = 10
