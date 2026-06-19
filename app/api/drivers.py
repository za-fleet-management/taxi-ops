from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_dispatcher_or_above, require_owner
from app.database import get_db
from app.models.driver import Driver
from app.models.employee import Employee
from app.models.user import User
from app.schemas.driver import DriverCreate, DriverResponse, DriverUpdate

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=list[DriverResponse])
def list_drivers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Driver)
        .filter(Driver.organisation_id == user.organisation_id)
        .all()
    )


@router.post("", response_model=DriverResponse, status_code=status.HTTP_201_CREATED)
def create_driver(
    body: DriverCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    driver = Driver(
        organisation_id=user.organisation_id,
        name=body.name,
        phone=body.phone,
        assigned_taxi_id=body.assigned_taxi_id,
        status=body.status,
    )
    db.add(driver)
    db.flush()

    employee = Employee(
        organisation_id=user.organisation_id,
        driver_id=driver.id,
        hire_date=date.today(),
    )
    db.add(employee)
    db.commit()
    db.refresh(driver)
    return driver


@router.patch("/{driver_id}", response_model=DriverResponse)
def update_driver(
    driver_id: str,
    body: DriverUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    driver = (
        db.query(Driver)
        .filter(
            Driver.id == driver_id,
            Driver.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not driver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if body.name is not None:
        driver.name = body.name
    if body.phone is not None:
        driver.phone = body.phone
    if body.assigned_taxi_id is not None:
        driver.assigned_taxi_id = body.assigned_taxi_id
    if body.status is not None:
        driver.status = body.status
    db.commit()
    db.refresh(driver)
    return driver
