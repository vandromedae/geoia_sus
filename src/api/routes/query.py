from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import get_db, get_llm_client
from src.llm.base import LLMClient
from src.llm.orchestrator import processar_pergunta
from src.schemas import QueryRequest, QueryResponse
from src.services.cache import cache_get, cache_set, make_key, normalizar_texto

router = APIRouter(tags=["query"])


@router.post("/query", response_model=QueryResponse)
async def query(
    req: QueryRequest,
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm_client),
):
    # Pergunta idem (sem acento/caixa/espaço) = mesma resposta: repetir a
    # pergunta não deve repetir a chamada ao LLM e gastar cotas do tier free.
    chave = make_key("query", normalizar_texto(req.pergunta))
    em_cache = cache_get(chave)
    if em_cache is not None:
        return QueryResponse(**em_cache)

    resposta = await processar_pergunta(req.pergunta, db=db, llm=llm)
    # Resposta de fallback (LLM sem texto) é transitória — cachear por 30 min
    # faria o usuário receber "não foi possível gerar uma resposta" para
    # sempre, mesmo quando o LLM voltasse.
    if not resposta.resposta_de_fallback:
        cache_set(chave, resposta.model_dump())
    return resposta
