import logging

from fastapi import APIRouter
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
        return {"status": "error", "database": "unavailable"}
