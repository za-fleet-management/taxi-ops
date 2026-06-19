from datetime import date, datetime

from pydantic import BaseModel, Field


class MechanicPaymentCreate(BaseModel):
    depot_id: str = Field(..., min_length=1)
    taxi_id: str | None = None
    mechanic_name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    amount_cents: int = Field(..., gt=0)
    payment_date: date
    payment_method: str = Field(default="cash", pattern="^(cash|eft|other)$")


class MechanicPaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    depot_id: str
    taxi_id: str | None
    mechanic_name: str
    description: str | None
    amount_cents: int
    payment_date: date
    payment_method: str
    created_by: str
    created_at: datetime


class MechanicPaymentWithDetails(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    depot_id: str
    depot_name: str
    taxi_id: str | None
    taxi_registration: str | None
    mechanic_name: str
    description: str | None
    amount_cents: int
    payment_date: date
    payment_method: str
    created_by: str
    created_at: datetime
