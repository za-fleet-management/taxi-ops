from datetime import datetime

from pydantic import BaseModel, Field


class RemunerationPackageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_salary_cents: int = Field(..., ge=0)
    payment_frequency: str = Field(default="monthly", pattern="^(weekly|monthly)$")


class RemunerationPackageUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    base_salary_cents: int | None = Field(None, ge=0)
    payment_frequency: str | None = Field(None, pattern="^(weekly|monthly)$")


class RemunerationPackageResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    name: str
    base_salary_cents: int
    payment_frequency: str
    created_at: datetime
