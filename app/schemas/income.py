from datetime import date, datetime

from pydantic import BaseModel, Field


class IncomeCreate(BaseModel):
    id: str | None = None
    taxi_id: str
    driver_id: str
    date: date
    total_cash: int = Field(..., ge=0)
    notes: str | None = None
    route_id: str | None = None


class IncomeResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    driver_id: str
    date: date
    total_cash: int
    notes: str | None
    captured_by: str
    created_at: datetime
