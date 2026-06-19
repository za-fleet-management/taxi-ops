from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.database import get_db
from app.models.admin_helpers import log_audit
from app.models.user import User, UserRole, UserStatus
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    users = (
        db.query(User)
        .filter(
            User.organisation_id == user.organisation_id,
            User.id != user.id,
        )
        .order_by(User.created_at.desc())
        .all()
    )
    return [
        UserResponse(
            id=u.id,
            name=u.name,
            phone=u.phone,
            role=u.role,
            status=u.status,
            created_at=u.created_at.isoformat(),
        )
        for u in users
    ]


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    user: User = Depends(get_current_user),
):
    return UserResponse(
        id=user.id,
        name=user.name,
        phone=user.phone,
        role=user.role,
        status=user.status,
        created_at=user.created_at.isoformat(),
    )


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    target = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=target.id,
        name=target.name,
        phone=target.phone,
        role=target.role,
        status=target.status,
        created_at=target.created_at.isoformat(),
    )


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    target = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    changes = {}
    if body.name is not None:
        changes["name"] = body.name
        target.name = body.name
    if body.phone is not None:
        existing = db.query(User).filter(User.phone == body.phone, User.id != user_id).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already in use")
        changes["phone"] = body.phone
        target.phone = body.phone

    if target.id == user.id:
        if body.role is not None or body.status is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify your own role or status",
            )
    else:
        if body.role is not None:
            changes["role"] = body.role
            target.role = body.role
        if body.status is not None:
            changes["status"] = body.status
            target.status = body.status

    db.flush()

    if changes:
        log_audit(db, user.organisation_id, user.id, "user.updated", "user", target.id, changes)

    db.commit()
    db.refresh(target)

    return UserResponse(
        id=target.id,
        name=target.name,
        phone=target.phone,
        role=target.role,
        status=target.status,
        created_at=target.created_at.isoformat(),
    )


@router.delete("/{user_id}")
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    target = (
        db.query(User)
        .filter(
            User.id == user_id,
            User.organisation_id == user.organisation_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if target.id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate yourself",
        )

    target.status = UserStatus.INACTIVE.value
    log_audit(db, user.organisation_id, user.id, "user.deactivated", "user", target.id)
    db.commit()

    return {"ok": True, "message": "User deactivated"}
