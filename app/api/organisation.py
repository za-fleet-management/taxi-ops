from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database import get_db
from app.models.admin_helpers import log_audit
from app.models.organisation import Organisation
from app.models.organisation_settings import OrganisationSettings
from app.models.user import User
from app.schemas.admin import (
    OrganisationProfileResponse,
    OrganisationProfileUpdate,
    OrganisationSettingsResponse,
    OrganisationSettingsUpdate,
)

router = APIRouter(prefix="/organisation", tags=["organisation"])


@router.get("/profile")
def get_org_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> OrganisationProfileResponse:
    org = db.query(Organisation).filter(Organisation.id == user.organisation_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return OrganisationProfileResponse.model_validate(org)


@router.put("/profile")
def update_org_profile(
    body: OrganisationProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> OrganisationProfileResponse:
    org = db.query(Organisation).filter(Organisation.id == user.organisation_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    changes = {}
    if body.name is not None:
        changes["name"] = body.name
        org.name = body.name
    if body.region is not None:
        changes["region"] = body.region
        org.region = body.region
    if changes:
        log_audit(db, user.organisation_id, user.id, "profile.updated", "organisation", org.id, changes)
    db.commit()
    db.refresh(org)
    return OrganisationProfileResponse.model_validate(org)


@router.get("/settings")
def get_org_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> OrganisationSettingsResponse:
    settings = (
        db.query(OrganisationSettings)
        .filter(OrganisationSettings.organisation_id == user.organisation_id)
        .first()
    )
    if not settings:
        settings = OrganisationSettings(
            organisation_id=user.organisation_id,
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return OrganisationSettingsResponse.model_validate(settings)


@router.put("/settings")
def update_org_settings(
    body: OrganisationSettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> OrganisationSettingsResponse:
    settings = (
        db.query(OrganisationSettings)
        .filter(OrganisationSettings.organisation_id == user.organisation_id)
        .first()
    )
    if not settings:
        settings = OrganisationSettings(organisation_id=user.organisation_id)
        db.add(settings)
    changes = {}
    if body.vat_registered is not None:
        changes["vat_registered"] = body.vat_registered
        settings.vat_registered = body.vat_registered
    if body.vat_number is not None:
        changes["vat_number"] = body.vat_number
        settings.vat_number = body.vat_number
    if body.financial_year_end is not None:
        changes["financial_year_end"] = body.financial_year_end.isoformat()
        settings.financial_year_end = body.financial_year_end
    if body.default_currency is not None:
        changes["default_currency"] = body.default_currency
        settings.default_currency = body.default_currency
    if changes:
        log_audit(db, user.organisation_id, user.id, "settings.updated", "organisation", settings.organisation_id, changes)
    db.commit()
    db.refresh(settings)
    return OrganisationSettingsResponse.model_validate(settings)
