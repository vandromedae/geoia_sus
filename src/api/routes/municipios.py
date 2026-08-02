from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.models import Municipio
from src.schemas import MunicipioResponse

router = APIRouter(prefix="/municipios", tags=["municipios"])


@router.get("/", response_model=list[MunicipioResponse])
def listar_municipios(db: Session = Depends(get_db)):
    return db.query(Municipio).all()


@router.get("/{cod_ibge}", response_model=MunicipioResponse)
def buscar_municipio(cod_ibge: str, db: Session = Depends(get_db)):
    mun = db.get(Municipio, cod_ibge)
    if not mun:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Município não encontrado")
    return mun
