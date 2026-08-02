from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_llm_client
from src.llm.base import LLMClient
from src.llm.orchestrator import processar_pergunta
from src.schemas import QueryRequest, QueryResponse

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    return await processar_pergunta(req.pergunta, db=db, llm=llm)
