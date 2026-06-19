from datetime import date, datetime

from pydantic import BaseModel, Field


class SparePartPurchaseCreate(BaseModel):
    depot_id: str = Field(..., min_length=1)
    taxi_id: str | None = None
    description: str = Field(..., min_length=1, max_length=500)
    cost_total_cents: int = Field(..., ge=0)
    date: date


class SparePartPurchaseResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    depot_id: str
    taxi_id: str | None
    description: str
    cost_total_cents: int
    date: date
    created_by: str
    created_at: datetime


class SparePartPurchaseWithDetails(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    depot_id: str
    depot_name: str
    taxi_id: str | None
    taxi_registration: str | None
    description: str
    cost_total_cents: int
    date: date
    created_by: str
    created_at: datetime
