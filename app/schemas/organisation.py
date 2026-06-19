from datetime import datetime

from pydantic import BaseModel


class OrganisationResponse(BaseModel):
    id: str
    name: str
    region: str
    created_at: datetime
