from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_owner
from app.database import get_db
from app.models.admin_helpers import log_audit
from app.models.subscription import OrganisationSubscription, SubscriptionPayment
from app.models.taxi import Taxi
from app.models.user import User
from app.schemas.subscription import (
    PaymentConfirm,
    PaymentCreate,
    PlanQuoteRequest,
    PlanQuoteResponse,
    SubscriptionResponse,
    price_per_taxi_cents,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

ALLOWED_PLANS = {1, 3, 6, 12}


def _get_sub(db: Session, org_id: str) -> OrganisationSubscription | None:
    return db.query(OrganisationSubscription).filter(
        OrganisationSubscription.organisation_id == org_id,
    ).first()


def _add_months(source: date, months: int) -> date:
    """Add N months to a date, clamping day to month length."""
    total = source.year * 12 + source.month + months
    y = (total - 1) // 12
    m = ((total - 1) % 12) + 1
    import calendar
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(source.day, last))


@router.get("/current")
def current_subscription(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    sub = _get_sub(db, effective_org_id)
    if not sub:
        return None
    today = date.today()
    return dict(
        id=sub.id,
        organisation_id=sub.organisation_id,
        plan_months=sub.plan_months,
        price_per_taxi_cents=sub.price_per_taxi_cents,
        taxi_count=sub.taxi_count,
        total_amount_cents=sub.total_amount_cents,
        period_start=sub.period_start.isoformat(),
        period_end=sub.period_end.isoformat(),
        status=sub.status,
        expired=sub.period_end < today,
        days_remaining=(sub.period_end - today).days if sub.period_end >= today else 0,
        created_at=sub.created_at.isoformat(),
        updated_at=sub.updated_at.isoformat(),
    )


@router.post("/quote")
def get_quote(
    body: PlanQuoteRequest,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    if body.plan_months not in ALLOWED_PLANS:
        raise HTTPException(status_code=400, detail="Plan must be 1, 3, 6, or 12 months")

    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    taxi_count = (
        db.query(Taxi)
        .filter(Taxi.organisation_id == effective_org_id, Taxi.status == "active")
        .count()
    )
    ppc = price_per_taxi_cents(body.plan_months)
    total = taxi_count * ppc * body.plan_months

    return PlanQuoteResponse(
        plan_months=body.plan_months,
        price_per_taxi_cents=ppc,
        taxi_count=taxi_count,
        total_cents=total,
        total_display=f"R {total // 100:,}",
    )


@router.post("/payments")
def record_payment(
    body: PaymentCreate,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    if body.plan_months not in ALLOWED_PLANS:
        raise HTTPException(status_code=400, detail="Plan must be 1, 3, 6, or 12 months")

    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id

    taxi_count = (
        db.query(Taxi)
        .filter(Taxi.organisation_id == effective_org_id, Taxi.status == "active")
        .count()
    )
    ppc = price_per_taxi_cents(body.plan_months)
    expected = taxi_count * ppc * body.plan_months

    if body.amount_cents < expected:
        raise HTTPException(
            status_code=400,
            detail=f"Amount too low. Expected at least R {expected // 100:,} for {taxi_count} taxi(s)",
        )

    sub = _get_sub(db, effective_org_id)
    today = date.today()

    if sub and sub.status == "active" and sub.period_end >= today:
        period_start = sub.period_end + timedelta(days=1)
    else:
        period_start = body.payment_date

    period_end = _add_months(period_start, body.plan_months) - timedelta(days=1)

    if not sub:
        sub = OrganisationSubscription(
            organisation_id=effective_org_id,
            plan_months=body.plan_months,
            price_per_taxi_cents=ppc,
            taxi_count=taxi_count,
            total_amount_cents=expected,
            period_start=period_start,
            period_end=period_end,
            status="active",
        )
        db.add(sub)
        db.flush()
    else:
        sub.plan_months = body.plan_months
        sub.price_per_taxi_cents = ppc
        sub.taxi_count = taxi_count
        sub.total_amount_cents = expected
        sub.period_start = period_start
        sub.period_end = period_end
        sub.status = "active"

    payment = SubscriptionPayment(
        organisation_id=effective_org_id,
        subscription_id=sub.id,
        amount_cents=body.amount_cents,
        reference=body.reference,
        payment_date=body.payment_date,
        bank_confirmed=False,
        confirmed=False,
    )
    db.add(payment)
    db.flush()

    log_audit(db, effective_org_id, user.id, "payment.recorded", "payment", payment.id, {
        "amount_cents": body.amount_cents,
        "reference": body.reference,
        "plan_months": body.plan_months,
    })
    db.commit()
    db.refresh(payment)

    return {
        "ok": True,
        "payment_id": payment.id,
        "subscription_id": sub.id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
    }


@router.get("/payments")
def list_payments(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    payments = (
        db.query(SubscriptionPayment)
        .filter(SubscriptionPayment.organisation_id == effective_org_id)
        .order_by(SubscriptionPayment.created_at.desc())
        .all()
    )
    return [
        {
            "id": p.id,
            "amount_cents": p.amount_cents,
            "reference": p.reference,
            "payment_date": p.payment_date.isoformat(),
            "confirmed": p.confirmed,
            "notes": p.notes,
            "created_at": p.created_at.isoformat(),
        }
        for p in payments
    ]


@router.patch("/payments/{payment_id}/confirm")
def confirm_payment(
    payment_id: str,
    body: PaymentConfirm,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    payment = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.id == payment_id,
            SubscriptionPayment.organisation_id == effective_org_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    payment.confirmed = True
    payment.confirmed_by = user.id
    payment.confirmed_at = datetime.now(timezone.utc)
    payment.notes = body.notes or payment.notes
    log_audit(db, effective_org_id, user.id, "payment.confirmed", "payment", payment.id, {
        "amount_cents": payment.amount_cents,
        "reference": payment.reference,
    })
    db.commit()

    return {"ok": True}


@router.patch("/payments/{payment_id}/bank-confirm")
def bank_confirm_payment(
    payment_id: str,
    body: PaymentConfirm,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    payment = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.id == payment_id,
            SubscriptionPayment.organisation_id == effective_org_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    payment.bank_confirmed = True
    payment.bank_confirmed_by = user.id
    payment.bank_confirmed_at = datetime.now(timezone.utc)
    payment.notes = body.notes or payment.notes
    log_audit(db, effective_org_id, user.id, "payment.bank_confirmed", "payment", payment.id, {
        "amount_cents": payment.amount_cents,
        "reference": payment.reference,
    })
    db.commit()

    return {"ok": True}


@router.get("/invoices")
def list_invoices(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    payments = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.organisation_id == effective_org_id,
            SubscriptionPayment.confirmed == True,
        )
        .order_by(SubscriptionPayment.payment_date.desc())
        .all()
    )
    sub = (
        db.query(OrganisationSubscription)
        .filter(OrganisationSubscription.organisation_id == effective_org_id)
        .first()
    )
    return [
        {
            "payment_id": p.id,
            "invoice_number": f"INV-{p.id[:8].upper()}",
            "amount_cents": p.amount_cents,
            "payment_date": p.payment_date.isoformat(),
            "reference": p.reference,
            "confirmed_at": p.confirmed_at.isoformat() if p.confirmed_at else None,
            "period_start": sub.period_start.isoformat() if sub else None,
            "period_end": sub.period_end.isoformat() if sub else None,
        }
        for p in payments
    ]


@router.get("/invoices/{payment_id}/pdf")
def download_invoice_pdf(
    payment_id: str,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    from app.services.invoice_pdf import generate_invoice_pdf

    effective_org_id = org_id if (user.role == "superadmin" and org_id) else user.organisation_id
    payment = (
        db.query(SubscriptionPayment)
        .filter(
            SubscriptionPayment.id == payment_id,
            SubscriptionPayment.organisation_id == effective_org_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    from app.models.organisation import Organisation
    from app.models.organisation_settings import OrganisationSettings
    from app.models.subscription import OrganisationSubscription

    org = db.query(Organisation).filter(Organisation.id == effective_org_id).first()
    settings = (
        db.query(OrganisationSettings)
        .filter(OrganisationSettings.organisation_id == effective_org_id)
        .first()
    )
    sub = (
        db.query(OrganisationSubscription)
        .filter(OrganisationSubscription.organisation_id == effective_org_id)
        .first()
    )

    pdf_bytes = generate_invoice_pdf(
        org_name=org.name if org else "Unknown",
        org_region=org.region if org else "",
        vat_number=settings.vat_number if settings and settings.vat_registered else None,
        invoice_number=f"INV-{payment.id[:8].upper()}",
        amount_cents=payment.amount_cents,
        payment_date=payment.payment_date,
        reference=payment.reference,
        period_start=sub.period_start if sub else None,
        period_end=sub.period_end if sub else None,
    )

    from fastapi.responses import Response
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice-{payment.id[:8]}.pdf"',
        },
    )
