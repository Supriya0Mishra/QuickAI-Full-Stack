from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Used by Docker, Coolify and uptime checks."""
    return {"status": "ok", "environment": get_settings().environment}
