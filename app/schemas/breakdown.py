from datetime import datetime

from pydantic import BaseModel, Field


class BreakdownCreate(BaseModel):
    id: str | None = None
    taxi_id: str
    start_time: datetime
    reason: str | None = None


class BreakdownClose(BaseModel):
    end_time: datetime
    cost_total: int = Field(..., ge=0)
    parts_used: str | None = None


class BreakdownResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    taxi_id: str
    start_time: datetime
    end_time: datetime | None
    reason: str | None
    cost_total: int | None
    parts_used: str | None
    captured_by: str
    created_at: datetime
