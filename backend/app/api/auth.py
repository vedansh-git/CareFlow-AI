from fastapi import APIRouter, Depends
from typing import Dict, Any
from app.core.security import get_current_user
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)) -> UserResponse:
    """
    Protected Endpoint: GET /api/me
    Validates Supabase Bearer token and returns current user identity.
    """
    return UserResponse(
        id=current_user.get("id"),
        email=current_user.get("email"),
        full_name=current_user.get("full_name"),
        role=current_user.get("app_role", "patient"),
        authenticated=True
    )
