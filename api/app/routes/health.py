import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness: the process is up. Used by Docker's healthcheck.

    Deliberately does not touch the database, so a slow or restarting database
    doesn't make Docker restart a healthy API container.
    """
    return {"status": "ok", "environment": get_settings().environment}


@router.get("/health/ready")
async def ready(session: Annotated[AsyncSession, Depends(get_session)]) -> JSONResponse:
    """Readiness: the API can reach the database. Used by deploys and uptime checks."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Database readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": "unreachable"},
        )
    return JSONResponse(content={"status": "ok", "database": "ok"})
