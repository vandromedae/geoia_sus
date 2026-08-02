from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import health, municipios, query
from src.config import settings

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

app.include_router(health.router)
app.include_router(municipios.router)
app.include_router(query.router)
