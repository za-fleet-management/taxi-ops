from datetime import date, datetime

from pydantic import BaseModel, Field


class TaxiCreate(BaseModel):
    registration_number: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=255)
    status: str = Field(default="active", pattern="^(active|breakdown|retired)$")
    assigned_route_id: str | None = None
    license_disk_number: str | None = Field(None, max_length=100)
    license_disk_expiry: date | None = None


class TaxiUpdate(BaseModel):
    registration_number: str | None = Field(None, min_length=1, max_length=50)
    model: str | None = Field(None, min_length=1, max_length=255)
    status: str | None = Field(None, pattern="^(active|breakdown|retired)$")
    assigned_route_id: str | None = None
    license_disk_number: str | None = Field(None, max_length=100)
    license_disk_expiry: date | None = None


class TaxiResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    registration_number: str
    model: str
    status: str
    assigned_route_id: str | None
    license_disk_number: str | None
    license_disk_expiry: date | None
    created_at: datetime
