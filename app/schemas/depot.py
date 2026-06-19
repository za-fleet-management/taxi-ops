from datetime import datetime

from pydantic import BaseModel, Field


class DepotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    depot_type: str = Field(default="mixed", pattern="^(parking|workshop|mixed)$")
    address: str | None = Field(None, max_length=500)


class DepotUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    depot_type: str | None = Field(None, pattern="^(parking|workshop|mixed)$")
    address: str | None = Field(None, max_length=500)


class DepotResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    name: str
    depot_type: str
    address: str | None
    created_at: datetime
