from datetime import datetime

from pydantic import BaseModel, Field


class DriverCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: str = Field(..., max_length=20)
    assigned_taxi_id: str | None = None
    status: str = Field(default="active", pattern="^(active|inactive)$")


class DriverUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = Field(None, max_length=20)
    assigned_taxi_id: str | None = None
    status: str | None = Field(None, pattern="^(active|inactive)$")


class DriverResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    name: str
    phone: str
    assigned_taxi_id: str | None
    status: str
    created_at: datetime
