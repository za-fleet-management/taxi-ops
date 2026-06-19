import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_owner
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.admin_helpers import log_audit
from app.models.invite import InviteToken
from app.models.organisation import Organisation
from app.models.user import User, UserRole
from app.schemas.auth import AdminLoginRequest, LoginRequest, SignupRequest, TokenResponse
from app.schemas.invite import AcceptInviteRequest, InviteRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

    org = Organisation(name=body.organisation_name, region=body.region)
    db.add(org)
    db.flush()

    user = User(
        organisation_id=org.id,
        role=UserRole.OWNER.value,
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    db.commit()

    access_token = create_access_token(
        user_id=user.id,
        organisation_id=org.id,
        role=user.role,
    )
    return TokenResponse(access_token=access_token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.phone).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    access_token = create_access_token(
        user_id=user.id,
        organisation_id=user.organisation_id,
        role=user.role,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=720 * 60,
        samesite="lax",
    )
    return TokenResponse(access_token=access_token)


@router.post("/admin-login", response_model=TokenResponse)
def admin_login(body: AdminLoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.phone == body.email).first()
    if not user or user.role != UserRole.SUPERADMIN.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_access_token(
        user_id=user.id,
        organisation_id=user.organisation_id,
        role=user.role,
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=720 * 60,
        samesite="lax",
    )
    return TokenResponse(access_token=access_token)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "organisation_id": user.organisation_id,
        "role": user.role,
        "name": user.name,
        "phone": user.phone,
    }


@router.post("/invite")
def invite(
    body: InviteRequest,
    user: User = Depends(require_owner),
    db: Session = Depends(get_db),
):
    token = secrets.token_urlsafe(32)
    invite = InviteToken(
        organisation_id=user.organisation_id,
        token=token,
        created_by=user.id,
        role=body.role,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.flush()
    log_audit(db, user.organisation_id, user.id, "user.invited", "user", invite.id, {
        "role": body.role,
        "name": body.name,
        "phone": body.phone,
    })
    db.commit()
    return {"invite_url": f"/accept-invite?token={token}"}


@router.post("/accept-invite")
def accept_invite(
    body: AcceptInviteRequest,
    db: Session = Depends(get_db),
):
    invite = (
        db.query(InviteToken)
        .filter(
            InviteToken.token == body.token,
            InviteToken.used_at.is_(None),
            InviteToken.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if not invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    existing = db.query(User).filter(User.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone already registered")

    user = User(
        organisation_id=invite.organisation_id,
        role=invite.role,
        name=body.name,
        phone=body.phone,
        password_hash=hash_password(body.password),
    )
    db.add(user)

    invite.used_at = datetime.now(timezone.utc)
    db.commit()

    access_token = create_access_token(
        user_id=user.id,
        organisation_id=user.organisation_id,
        role=user.role,
    )
    return TokenResponse(access_token=access_token)
