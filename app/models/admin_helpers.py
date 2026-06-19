from json import dumps

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_audit(
    db: Session,
    organisation_id: str,
    user_id: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    entry = AuditLog(
        organisation_id=organisation_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=dumps(details) if details else None,
    )
    db.add(entry)
    db.flush()
    return entry
