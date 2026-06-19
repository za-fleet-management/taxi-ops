from datetime import date, datetime

from pydantic import BaseModel, Field


class InsuranceCreate(BaseModel):
    taxi_id: str = Field(..., min_length=1)
    insurer: str = Field(..., min_length=1, max_length=255)
    policy_number: str | None = Field(None, max_length=255)
    monthly_premium_cents: int = Field(..., ge=0)
    start_date: date
    end_date: date | None = None


class InsuranceUpdate(BaseModel):
    insurer: str | None = Field(None, min_length=1, max_length=255)
    policy_number: str | None = Field(None, max_length=255)
    monthly_premium_cents: int | None = Field(None, ge=0)
    end_date: date | None = None


class InsuranceResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    insurer: str
    policy_number: str | None
    monthly_premium_cents: int
    start_date: date
    end_date: date | None
    created_at: datetime


class InsuranceWithTaxi(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    registration_number: str
    insurer: str
    policy_number: str | None
    monthly_premium_cents: int
    start_date: date
    end_date: date | None
    created_at: datetime
