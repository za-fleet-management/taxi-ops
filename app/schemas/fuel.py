from datetime import date, datetime

from pydantic import BaseModel, Field


class FuelCreate(BaseModel):
    taxi_id: str
    date: date
    litres: float = Field(..., gt=0)
    cost_total: int = Field(..., ge=0)
    odometer_km: int | None = None


class FuelResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    date: date
    litres: float
    cost_total: int
    odometer_km: int | None
    captured_by: str
    created_at: datetime
