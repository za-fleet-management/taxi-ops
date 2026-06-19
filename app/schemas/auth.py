from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    organisation_name: str = Field(..., min_length=1, max_length=255)
    region: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., min_length=1, max_length=20)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    phone: str
    password: str


class AdminLoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
