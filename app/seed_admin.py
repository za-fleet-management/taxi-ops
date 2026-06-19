"""Seeds the platform admin (superadmin) account on first run."""

import logging

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.organisation import Organisation
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

ADMIN_PHONE = "mobiusndou@gmail.com"
ADMIN_PASSWORD = "Mobius5627084@"
ADMIN_NAME = "Platform Admin"
PLATFORM_ORG_NAME = "TaxiOps Platform"


def seed_admin(db: Session) -> bool:
    """Create the superadmin account + platform org if they don't exist.
    Returns True if created, False if already present."""
    existing = db.query(User).filter(User.phone == ADMIN_PHONE).first()
    if existing:
        return False

    org = Organisation(name=PLATFORM_ORG_NAME, region="Platform")
    db.add(org)
    db.flush()

    user = User(
        organisation_id=org.id,
        role=UserRole.SUPERADMIN.value,
        name=ADMIN_NAME,
        phone=ADMIN_PHONE,
        password_hash=hash_password(ADMIN_PASSWORD),
    )
    db.add(user)
    db.commit()
    logger.info("Superadmin account created: %s", ADMIN_PHONE)
    return True
