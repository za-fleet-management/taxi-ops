from pydantic import BaseModel, Field

from app.models.user import UserRole, UserStatus


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    role: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, min_length=1, max_length=20)
    role: str | None = Field(None, pattern=f"^({'|'.join(r.value for r in UserRole)})$")
    status: str | None = Field(None, pattern=f"^({'|'.join(s.value for s in UserStatus)})$")
