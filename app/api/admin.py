from datetime import date, datetime, timedelta, timezone
from json import dumps

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database import get_db
from app.models.admin_helpers import log_audit
from app.models.audit_log import AuditLog
from app.models.breakdown import Breakdown
from app.models.driver import Driver
from app.models.income import DailyIncome
from app.models.notification import Notification
from app.models.subscription import OrganisationSubscription, SubscriptionPayment
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.admin import (
    AdminDashboardResponse,
    AuditLogEntry,
    NotificationResponse,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def admin_dashboard(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
) -> AdminDashboardResponse:
    org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    today = date.today()

    taxis = db.query(Taxi).filter(Taxi.organisation_id == org_id).all()
    drivers = db.query(Driver).filter(Driver.organisation_id == org_id).all()

    month_start = today.replace(day=1)
    income_total = (
        db.query(func.coalesce(func.sum(DailyIncome.total_cash), 0))
        .filter(
            DailyIncome.organisation_id == org_id,
            DailyIncome.date >= month_start,
            DailyIncome.date <= today,
        )
        .scalar()
    )
    open_breakdowns = (
        db.query(func.count(Breakdown.id))
        .filter(
            Breakdown.organisation_id == org_id,
            Breakdown.end_time.is_(None),
        )
        .scalar()
    )

    unconfirmed = (
        db.query(func.count(SubscriptionPayment.id))
        .filter(
            SubscriptionPayment.organisation_id == org_id,
            SubscriptionPayment.confirmed == False,
        )
        .scalar()
    )

    bank_unconfirmed = (
        db.query(func.count(SubscriptionPayment.id))
        .filter(
            SubscriptionPayment.organisation_id == org_id,
            SubscriptionPayment.bank_confirmed == False,
            SubscriptionPayment.confirmed == False,
        )
        .scalar()
    )

    sub = (
        db.query(OrganisationSubscription)
        .filter(OrganisationSubscription.organisation_id == org_id)
        .first()
    )
    sub_days_remaining = 0
    sub_expired = False
    if sub:
        sub_expired = sub.period_end < today
        sub_days_remaining = (
            (sub.period_end - today).days if sub.period_end >= today else 0
        )

    recent_audit = (
        db.query(AuditLog, User.name.label("user_name"))
        .join(User, User.id == AuditLog.user_id)
        .filter(AuditLog.organisation_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )
    audit_entries = [
        {
            "id": a.id,
            "user_name": user_name,
            "action": a.action,
            "entity_type": a.entity_type,
            "created_at": a.created_at.isoformat(),
        }
        for a, user_name in recent_audit
    ]

    notifications_q = (
        db.query(Notification)
        .filter(
            Notification.organisation_id == org_id,
            Notification.dismissed == False,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )

    return AdminDashboardResponse(
        active_taxis=sum(1 for t in taxis if t.status == "active"),
        total_taxis=len(taxis),
        active_drivers=sum(1 for d in drivers if d.status == "active"),
        total_drivers=len(drivers),
        income_this_month=income_total,
        open_breakdowns=open_breakdowns,
        unconfirmed_payments=unconfirmed,
        bank_unconfirmed_payments=bank_unconfirmed,
        sub_days_remaining=sub_days_remaining,
        sub_expired=sub_expired,
        recent_audit_entries=audit_entries,
        notifications=[
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "link": n.link,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications_q
        ],
    )


@router.get("/audit-log")
def list_audit_log(
    org_id: str | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    q = (
        db.query(AuditLog, User.name.label("user_name"))
        .join(User, User.id == AuditLog.user_id)
        .filter(AuditLog.organisation_id == effective_org_id)
    )
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if action:
        q = q.filter(AuditLog.action == action)

    total = q.count()
    rows = (
        q.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "entries": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "user_name": user_name,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "details": a.details,
                "created_at": a.created_at.isoformat(),
            }
            for a, user_name in rows
        ],
    }


@router.get("/notifications")
def list_notifications(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    notifications = (
        db.query(Notification)
        .filter(
            Notification.organisation_id == effective_org_id,
            Notification.dismissed == False,
        )
        .order_by(Notification.created_at.desc())
        .all()
    )
    return [
        NotificationResponse.model_validate(n) for n in notifications
    ]


@router.patch("/notifications/{notification_id}/dismiss")
def dismiss_notification(
    notification_id: str,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.organisation_id == effective_org_id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    notification.dismissed = True
    db.commit()
    return {"ok": True}
