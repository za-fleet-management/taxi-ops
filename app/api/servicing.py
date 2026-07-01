from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_dispatcher_or_above, require_owner
from app.database import get_db
from app.models.notification import Notification
from app.models.service import ServiceRecord, ServiceType, TaxiServiceSchedule
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.service import (
    ServiceRecordCreate,
    ServiceRecordResponse,
    ServiceRecordUpdate,
    ServiceRecordWithNames,
    ServiceTypeCreate,
    ServiceTypeResponse,
    ServiceTypeUpdate,
    TaxiServiceScheduleCreate,
    TaxiServiceScheduleResponse,
    TaxiServiceScheduleUpdate,
    TaxiServiceScheduleWithNames,
)

router = APIRouter(prefix="/servicing", tags=["servicing"])


# ── Helpers ──────────────────────────────────────────────────────────────────


def _ensure_taxi_belongs(taxi_id: str, org_id: str, db: Session) -> Taxi:
    taxi = db.query(Taxi).filter(
        Taxi.id == taxi_id, Taxi.organisation_id == org_id
    ).first()
    if not taxi:
        raise HTTPException(status_code=404, detail="Taxi not found")
    return taxi


def _ensure_service_type_belongs(st_id: str, org_id: str, db: Session) -> ServiceType:
    st = db.query(ServiceType).filter(
        ServiceType.id == st_id, ServiceType.organisation_id == org_id
    ).first()
    if not st:
        raise HTTPException(status_code=404, detail="Service type not found")
    return st


def _compute_next_due(
    st: ServiceType,
    last_date: date | None,
    last_km: int | None,
) -> tuple[date | None, int | None]:
    next_date = None
    next_km = None
    if st.interval_days and last_date:
        next_date = last_date + timedelta(days=st.interval_days)
    if st.interval_km and last_km is not None:
        next_km = last_km + st.interval_km
    return next_date, next_km


# ── Service Types ────────────────────────────────────────────────────────────


@router.get("/service-types", response_model=list[ServiceTypeResponse])
def list_service_types(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    include_inactive: bool = False,
):
    q = db.query(ServiceType).filter(
        ServiceType.organisation_id == user.organisation_id
    )
    if not include_inactive:
        q = q.filter(ServiceType.is_active == True)
    return q.order_by(ServiceType.name).all()


@router.post("/service-types", response_model=ServiceTypeResponse, status_code=status.HTTP_201_CREATED)
def create_service_type(
    body: ServiceTypeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    st = ServiceType(
        organisation_id=user.organisation_id,
        name=body.name,
        description=body.description,
        interval_km=body.interval_km,
        interval_days=body.interval_days,
        reminder_days_before=body.reminder_days_before,
    )
    db.add(st)
    db.commit()
    db.refresh(st)
    return st


@router.patch("/service-types/{st_id}", response_model=ServiceTypeResponse)
def update_service_type(
    st_id: str,
    body: ServiceTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    st = _ensure_service_type_belongs(st_id, user.organisation_id, db)
    if body.name is not None:
        st.name = body.name
    if body.description is not None:
        st.description = body.description
    if body.interval_km is not None:
        st.interval_km = body.interval_km
    if body.interval_days is not None:
        st.interval_days = body.interval_days
    if body.reminder_days_before is not None:
        st.reminder_days_before = body.reminder_days_before
    if body.is_active is not None:
        st.is_active = body.is_active
    db.commit()
    db.refresh(st)
    return st


# ── Taxi Service Schedules ───────────────────────────────────────────────────


@router.get("/schedules", response_model=list[TaxiServiceScheduleWithNames])
def list_schedules(
    taxi_id: str | None = None,
    overdue: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(
            TaxiServiceSchedule,
            Taxi.registration_number.label("registration_number"),
            ServiceType.name.label("service_type_name"),
        )
        .join(Taxi, Taxi.id == TaxiServiceSchedule.taxi_id)
        .join(ServiceType, ServiceType.id == TaxiServiceSchedule.service_type_id)
        .filter(TaxiServiceSchedule.organisation_id == user.organisation_id)
    )
    if taxi_id:
        q = q.filter(TaxiServiceSchedule.taxi_id == taxi_id)

    rows = q.order_by(TaxiServiceSchedule.next_due_date).all()

    result = []
    for sched, reg, st_name in rows:
        is_overdue = False
        if sched.next_due_date and sched.next_due_date < date.today():
            is_overdue = True
        if overdue is not None and is_overdue != overdue:
            continue
        result.append(TaxiServiceScheduleWithNames(
            id=sched.id,
            organisation_id=sched.organisation_id,
            taxi_id=sched.taxi_id,
            registration_number=reg,
            service_type_id=sched.service_type_id,
            service_type_name=st_name,
            last_service_date=sched.last_service_date,
            last_service_km=sched.last_service_km,
            next_due_date=sched.next_due_date,
            next_due_km=sched.next_due_km,
            created_at=sched.created_at,
        ))
    return result


@router.post("/schedules", response_model=TaxiServiceScheduleResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    body: TaxiServiceScheduleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    _ensure_taxi_belongs(body.taxi_id, user.organisation_id, db)
    _ensure_service_type_belongs(body.service_type_id, user.organisation_id, db)

    existing = db.query(TaxiServiceSchedule).filter(
        TaxiServiceSchedule.organisation_id == user.organisation_id,
        TaxiServiceSchedule.taxi_id == body.taxi_id,
        TaxiServiceSchedule.service_type_id == body.service_type_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Schedule already exists for this taxi and service type")

    next_due_date = body.next_due_date
    next_due_km = body.next_due_km

    if next_due_date is None and next_due_km is None and body.last_service_date:
        st = _ensure_service_type_belongs(body.service_type_id, user.organisation_id, db)
        next_due_date, next_due_km = _compute_next_due(
            st, body.last_service_date, body.last_service_km
        )

    sched = TaxiServiceSchedule(
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        service_type_id=body.service_type_id,
        last_service_date=body.last_service_date,
        last_service_km=body.last_service_km,
        next_due_date=next_due_date,
        next_due_km=next_due_km,
    )
    db.add(sched)
    db.commit()
    db.refresh(sched)
    return sched


@router.patch("/schedules/{sched_id}", response_model=TaxiServiceScheduleResponse)
def update_schedule(
    sched_id: str,
    body: TaxiServiceScheduleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    sched = (
        db.query(TaxiServiceSchedule)
        .filter(
            TaxiServiceSchedule.id == sched_id,
            TaxiServiceSchedule.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not sched:
        raise HTTPException(status_code=404)

    if body.last_service_date is not None:
        sched.last_service_date = body.last_service_date
    if body.last_service_km is not None:
        sched.last_service_km = body.last_service_km
    if body.next_due_date is not None or "next_due_date" in body.model_fields_set:
        sched.next_due_date = body.next_due_date
    if body.next_due_km is not None or "next_due_km" in body.model_fields_set:
        sched.next_due_km = body.next_due_km
    db.commit()
    db.refresh(sched)
    return sched


@router.delete("/schedules/{sched_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    sched_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    sched = (
        db.query(TaxiServiceSchedule)
        .filter(
            TaxiServiceSchedule.id == sched_id,
            TaxiServiceSchedule.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not sched:
        raise HTTPException(status_code=404)
    db.delete(sched)
    db.commit()


# ── Service Records ──────────────────────────────────────────────────────────


@router.get("/records", response_model=list[ServiceRecordWithNames])
def list_service_records(
    taxi_id: str | None = None,
    service_type_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = (
        db.query(
            ServiceRecord,
            Taxi.registration_number.label("registration_number"),
            ServiceType.name.label("service_type_name"),
        )
        .join(Taxi, Taxi.id == ServiceRecord.taxi_id)
        .join(ServiceType, ServiceType.id == ServiceRecord.service_type_id)
        .filter(ServiceRecord.organisation_id == user.organisation_id)
    )
    if taxi_id:
        q = q.filter(ServiceRecord.taxi_id == taxi_id)
    if service_type_id:
        q = q.filter(ServiceRecord.service_type_id == service_type_id)

    rows = q.order_by(ServiceRecord.service_date.desc()).all()
    return [
        ServiceRecordWithNames(
            id=r.id,
            organisation_id=r.organisation_id,
            taxi_id=r.taxi_id,
            registration_number=reg,
            service_type_id=r.service_type_id,
            service_type_name=st_name,
            schedule_id=r.schedule_id,
            service_date=r.service_date,
            odometer_km=r.odometer_km,
            cost_cents=r.cost_cents,
            vendor=r.vendor,
            notes=r.notes,
            captured_by=r.captured_by,
            created_at=r.created_at,
        )
        for r, reg, st_name in rows
    ]


@router.post("/records", response_model=ServiceRecordResponse, status_code=status.HTTP_201_CREATED)
def create_service_record(
    body: ServiceRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    _ensure_taxi_belongs(body.taxi_id, user.organisation_id, db)
    _ensure_service_type_belongs(body.service_type_id, user.organisation_id, db)

    if body.schedule_id:
        sched = (
            db.query(TaxiServiceSchedule)
            .filter(
                TaxiServiceSchedule.id == body.schedule_id,
                TaxiServiceSchedule.organisation_id == user.organisation_id,
            )
            .first()
        )
        if not sched:
            raise HTTPException(status_code=404, detail="Schedule not found")

    record = ServiceRecord(
        organisation_id=user.organisation_id,
        taxi_id=body.taxi_id,
        service_type_id=body.service_type_id,
        schedule_id=body.schedule_id,
        service_date=body.service_date,
        odometer_km=body.odometer_km,
        cost_cents=body.cost_cents,
        vendor=body.vendor,
        notes=body.notes,
        captured_by=user.id,
    )
    db.add(record)
    db.flush()

    if body.schedule_id:
        sched = (
            db.query(TaxiServiceSchedule)
            .filter(
                TaxiServiceSchedule.id == body.schedule_id,
                TaxiServiceSchedule.organisation_id == user.organisation_id,
            )
            .first()
        )
        if sched:
            st = _ensure_service_type_belongs(sched.service_type_id, user.organisation_id, db)
            sched.last_service_date = body.service_date
            sched.last_service_km = body.odometer_km
            next_date, next_km = _compute_next_due(st, body.service_date, body.odometer_km)
            if next_date:
                sched.next_due_date = next_date
            if next_km is not None:
                sched.next_due_km = next_km

    db.commit()
    db.refresh(record)
    return record


@router.patch("/records/{record_id}", response_model=ServiceRecordResponse)
def update_service_record(
    record_id: str,
    body: ServiceRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_dispatcher_or_above),
):
    record = (
        db.query(ServiceRecord)
        .filter(
            ServiceRecord.id == record_id,
            ServiceRecord.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=404)

    if body.service_date is not None:
        record.service_date = body.service_date
    if body.odometer_km is not None:
        record.odometer_km = body.odometer_km
    if body.cost_cents is not None:
        record.cost_cents = body.cost_cents
    if body.vendor is not None:
        record.vendor = body.vendor
    if body.notes is not None:
        record.notes = body.notes
    db.commit()
    db.refresh(record)
    return record


# ── Dashboard summary / overdue count ────────────────────────────────────────


@router.get("/overdue-count")
def overdue_service_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    count = (
        db.query(TaxiServiceSchedule)
        .filter(
            TaxiServiceSchedule.organisation_id == user.organisation_id,
            TaxiServiceSchedule.next_due_date < today,
        )
        .count()
    )
    return {"overdue_count": count}


# ── Reminder notifications ───────────────────────────────────────────────────


@router.post("/generate-reminders")
def generate_service_reminders(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    today = date.today()
    scheds = (
        db.query(TaxiServiceSchedule)
        .filter(
            TaxiServiceSchedule.organisation_id == user.organisation_id,
            TaxiServiceSchedule.next_due_date.isnot(None),
        )
        .all()
    )
    created = 0
    for sched in scheds:
        st = _ensure_service_type_belongs(sched.service_type_id, user.organisation_id, db)
        reminder_date = sched.next_due_date - timedelta(days=st.reminder_days_before)
        if reminder_date <= today:
            taxi = _ensure_taxi_belongs(sched.taxi_id, user.organisation_id, db)
            existing = db.query(Notification).filter(
                Notification.organisation_id == user.organisation_id,
                Notification.type == "service_reminder",
                Notification.link == f"/servicing?sched_id={sched.id}",
                Notification.dismissed == False,
            ).first()
            if not existing:
                notif = Notification(
                    organisation_id=user.organisation_id,
                    type="service_reminder",
                    title=f"Service due: {st.name}",
                    message=(
                        f"{st.name} is due for {taxi.registration_number}. "
                        f"Due date: {sched.next_due_date}"
                    ),
                    link=f"/servicing?sched_id={sched.id}",
                )
                db.add(notif)
                created += 1
    db.commit()
    return {"reminders_created": created}
