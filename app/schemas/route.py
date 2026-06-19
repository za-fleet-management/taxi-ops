from datetime import datetime

from pydantic import BaseModel


class RouteCreate(BaseModel):
    name: str
    distance_km: float | None = None


class RouteResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    organisation_id: str
    name: str
    distance_km: float | None
    created_at: datetime
