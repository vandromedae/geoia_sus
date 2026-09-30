import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.database import engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        logger.error("Health check failed", exc_info=True)
        # 503 e não 200: o orquestrador (e o `docker compose ps`) precisa
        # distinguir "API viva" de "API viva mas sem banco".
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "unavailable"},
        )
