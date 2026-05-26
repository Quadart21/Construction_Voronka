from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
import pyotp
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import session_scope
from backend.models import AdminUser


@dataclass(frozen=True)
class AdminCtx:
    id: int
    username: str

TOKEN_SETUP_2FA = "setup_2fa"
TOKEN_PENDING_2FA = "pending_2fa"
TOKEN_ACCESS = "access"


def jwt_secret() -> str:
    if settings.admin_jwt_secret.strip():
        return settings.admin_jwt_secret.strip()
    path = settings.data_dir / ".admin_jwt_secret"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    path.write_text(secret, encoding="utf-8")
    return secret


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > 72:
        raw = raw[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12)).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        raw = plain.encode("utf-8")
        if len(raw) > 72:
            raw = raw[:72]
        return bcrypt.checkpw(raw, hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _encode(payload: dict[str, Any], expires: timedelta) -> str:
    now = datetime.now(timezone.utc)
    body = {**payload, "iat": int(now.timestamp()), "exp": int((now + expires).timestamp())}
    return jwt.encode(body, jwt_secret(), algorithm="HS256")


def _decode(token: str) -> dict[str, Any]:
    return jwt.decode(token, jwt_secret(), algorithms=["HS256"])


def issue_access_token(admin: AdminUser) -> str:
    return _encode(
        {"typ": TOKEN_ACCESS, "sub": admin.username, "aid": admin.id},
        timedelta(days=max(1, settings.admin_access_token_days)),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    payload = _decode(token)
    if payload.get("typ") != TOKEN_ACCESS:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def issue_setup_2fa_token(username: str, secret: str) -> str:
    return _encode({"typ": TOKEN_SETUP_2FA, "sub": username, "sec": secret}, timedelta(minutes=20))


def issue_pending_2fa_token(admin_id: int, username: str) -> str:
    return _encode({"typ": TOKEN_PENDING_2FA, "sub": username, "aid": admin_id}, timedelta(minutes=15))


def verify_totp_code(secret: str, code: str) -> bool:
    if not code or not secret:
        return False
    return bool(pyotp.TOTP(secret).verify(code.strip().replace(" ", ""), valid_window=1))


def provisioning_uri(username: str, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=settings.app_name[:40] or "Admin")


def get_admin_by_username(session: Session, username: str) -> AdminUser | None:
    return session.scalar(select(AdminUser).where(AdminUser.username == username, AdminUser.is_active.is_(True)))


def bootstrap_env_admin_if_empty(session: Session) -> None:
    if session.scalar(select(func.count(AdminUser.id))) != 0:
        return
    user = settings.admin_panel_username.strip() or "admin"
    pwd = settings.admin_panel_password
    session.add(
        AdminUser(
            username=user,
            password_hash=hash_password(pwd),
            totp_secret=None,
            totp_confirmed=False,
            is_active=True,
        )
    )


def login_with_password(session: Session, username: str, password: str) -> dict[str, Any]:
    admin = get_admin_by_username(session, username.strip())
    if admin is None or not verify_password(password, admin.password_hash):
        return {"status": "invalid"}

    if not admin.totp_confirmed:
        secret = pyotp.random_base32()
        setup_token = issue_setup_2fa_token(admin.username, secret)
        return {
            "status": "must_setup_2fa",
            "setup_token": setup_token,
            "provisioning_uri": provisioning_uri(admin.username, secret),
            "secret_manual": secret,
        }

    partial = issue_pending_2fa_token(admin.id, admin.username)
    return {"status": "need_totp", "partial_token": partial}


def confirm_2fa_setup(session: Session, setup_token: str, code: str) -> str:
    payload = _decode(setup_token)
    if payload.get("typ") != TOKEN_SETUP_2FA:
        raise ValueError("invalid_setup_token")
    username = payload["sub"]
    secret = payload["sec"]
    if not verify_totp_code(secret, code):
        raise ValueError("invalid_totp")
    admin = session.scalar(select(AdminUser).where(AdminUser.username == username))
    if admin is None or not admin.is_active:
        raise ValueError("user_missing")
    admin.totp_secret = secret
    admin.totp_confirmed = True
    session.flush()
    return issue_access_token(admin)


def verify_2fa_login(session: Session, partial_token: str, code: str) -> str:
    payload = _decode(partial_token)
    if payload.get("typ") != TOKEN_PENDING_2FA:
        raise ValueError("invalid_partial_token")
    admin = session.get(AdminUser, payload["aid"])
    if admin is None or not admin.is_active or not admin.totp_secret:
        raise ValueError("user_missing")
    if not verify_totp_code(admin.totp_secret, code):
        raise ValueError("invalid_totp")
    return issue_access_token(admin)


def get_admin_from_access_token(session: Session, token: str) -> AdminUser:
    payload = decode_access_token(token)
    admin = session.get(AdminUser, payload["aid"])
    if admin is None or not admin.is_active:
        raise jwt.InvalidTokenError("admin inactive")
    if admin.username != payload["sub"]:
        raise jwt.InvalidTokenError("mismatch")
    return admin


def load_admin_ctx(token: str) -> AdminCtx:
    with session_scope() as session:
        admin = get_admin_from_access_token(session, token)
        return AdminCtx(id=admin.id, username=admin.username)
