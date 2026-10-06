from pydantic import BaseModel, EmailStr
from typing import Optional


class UserResponse(BaseModel):
    id: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "patient"
    authenticated: bool = True
