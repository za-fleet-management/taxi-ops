from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_accountant_or_above, require_owner
from app.database import get_db
from app.models.remuneration import RemunerationPackage
from app.models.user import User
from app.schemas.remuneration import (
    RemunerationPackageCreate,
    RemunerationPackageResponse,
    RemunerationPackageUpdate,
)

router = APIRouter(prefix="/remuneration-packages", tags=["remuneration"])


@router.get("", response_model=list[RemunerationPackageResponse])
def list_packages(
    db: Session = Depends(get_db),
    user: User = Depends(require_accountant_or_above),
):
    return (
        db.query(RemunerationPackage)
        .filter(RemunerationPackage.organisation_id == user.organisation_id)
        .order_by(RemunerationPackage.name)
        .all()
    )


@router.post("", response_model=RemunerationPackageResponse, status_code=status.HTTP_201_CREATED)
def create_package(
    body: RemunerationPackageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    existing = (
        db.query(RemunerationPackage)
        .filter(
            RemunerationPackage.organisation_id == user.organisation_id,
            RemunerationPackage.name == body.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A package with this name already exists",
        )

    pkg = RemunerationPackage(
        organisation_id=user.organisation_id,
        name=body.name,
        base_salary_cents=body.base_salary_cents,
        payment_frequency=body.payment_frequency,
    )
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg


@router.patch("/{package_id}", response_model=RemunerationPackageResponse)
def update_package(
    package_id: str,
    body: RemunerationPackageUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    pkg = (
        db.query(RemunerationPackage)
        .filter(
            RemunerationPackage.id == package_id,
            RemunerationPackage.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.name is not None:
        pkg.name = body.name
    if body.base_salary_cents is not None:
        pkg.base_salary_cents = body.base_salary_cents
    if body.payment_frequency is not None:
        pkg.payment_frequency = body.payment_frequency
    db.commit()
    db.refresh(pkg)
    return pkg
