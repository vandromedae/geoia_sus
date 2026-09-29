from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import health, municipios, query
from src.config import settings
from src.llm.errors import LLMError

app = FastAPI(
    title="GeoIA_SUS",
    description="Assistente de saúde geoespacial com IA generativa",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(LLMError)
async def tratar_llm_error(request: Request, exc: LLMError) -> JSONResponse:
    """429/413/504 com mensagem legível em vez de `500 Internal Server Error`."""
    headers = {}
    if exc.retry_after is not None:
        headers["Retry-After"] = f"{exc.retry_after:g}"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.user_message},
        headers=headers,
    )


app.include_router(health.router)
app.include_router(municipios.router)
app.include_router(query.router)
