from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models import Municipio
from src.schemas import MunicipioResponse
from src.services.cache import cache_get, cache_set, make_key

router = APIRouter(prefix="/municipios", tags=["municipios"])

# 645 municípios em SP — sem limite, o default serializava ~100 kB a cada
# chamada; com o cache o custo passa a ser só do primeiro acesso.
_LIMITE_MAXIMO = 645


@router.get("/", response_model=list[MunicipioResponse])
def listar_municipios(
    limite: int = Query(100, ge=1, le=_LIMITE_MAXIMO),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    chave = make_key("municipios", limite, offset)
    em_cache = cache_get(chave)
    if em_cache is not None:
        return [MunicipioResponse(**item) for item in em_cache]

    # Ordenação explícita: sem ela o OFFSET pula/repete linhas entre chamadas.
    linhas = (
        db.query(Municipio)
        .order_by(Municipio.nm_mun, Municipio.cod_mun_ibge)
        .offset(offset)
        .limit(limite)
        .all()
    )
    payload = [MunicipioResponse.model_validate(m).model_dump() for m in linhas]
    cache_set(chave, payload)
    return payload


@router.get("/{cod_ibge}", response_model=MunicipioResponse)
def buscar_municipio(cod_ibge: str, db: Session = Depends(get_db)):
    chave = make_key("municipio", cod_ibge)
    em_cache = cache_get(chave)
    if em_cache is not None:
        return MunicipioResponse(**em_cache)

    mun = db.get(Municipio, cod_ibge)
    if not mun:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    payload = MunicipioResponse.model_validate(mun).model_dump()
    cache_set(chave, payload)
    return payload
