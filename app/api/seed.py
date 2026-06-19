from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database import get_db
from app.models.user import User
from app.seed import clear_organisation_data, seed_organisation, seed_status

router = APIRouter(prefix="/seed", tags=["seed"])


@router.get("/status")
def get_seed_status(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return seed_status(db, effective_org_id)


@router.post("/load")
def load_seed_data(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    result = seed_organisation(db, effective_org_id, user.id)
    if not result["seeded"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result["reason"],
        )
    return result


@router.delete("/clear")
def clear_seed_data(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    return clear_organisation_data(db, effective_org_id)
