from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> dict:
    """The signed-in user and their plan."""
    return {
        "success": True,
        "user": {"id": user.user_id, "plan": user.plan, "is_premium": user.is_premium},
    }
