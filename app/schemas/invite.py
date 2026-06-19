from pydantic import BaseModel, Field

from app.models.user import UserRole


class InviteRequest(BaseModel):
    name: str
    phone: str
    role: str = Field(
        default="manager",
        pattern=f"^({'|'.join(r.value for r in UserRole if r not in (UserRole.OWNER, UserRole.SUPERADMIN))})$",
    )


class AcceptInviteRequest(BaseModel):
    token: str
    name: str
    phone: str
    password: str
