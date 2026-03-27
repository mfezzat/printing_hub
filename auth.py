"""
Auth router — phone OTP registration/login, JWT issuance.
Endpoints:
  POST /auth/send-otp
  POST /auth/verify-otp
  POST /auth/refresh
  POST /auth/logout
"""
import hashlib, secrets, random
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, field_validator
import phonenumbers
from passlib.hash import bcrypt
from jose import jwt, JWTError

from db import get_db
from config import get_settings
from models.models import User, OtpAttempt, RefreshToken, AuditLog
from services.sms import send_otp_sms
from services.whatsapp import send_whatsapp_opt_in

router   = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# ── Pydantic schemas ─────────────────────────────────────────
class SendOtpRequest(BaseModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        try:
            parsed = phonenumbers.parse(v, "EG")
            if not phonenumbers.is_valid_number(parsed):
                raise ValueError("Invalid phone number")
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            raise ValueError("Invalid phone number format")

class VerifyOtpRequest(BaseModel):
    phone:           str
    code:            str
    name:            str | None = None
    whatsapp_opt_in: bool = False
    language:        str  = "ar"
    student_id:      str | None = None

class RefreshRequest(BaseModel):
    refresh_token: str

# ── Helpers ──────────────────────────────────────────────────
def _create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def _create_refresh_token() -> tuple[str, str]:
    raw   = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

def _hash_student_id(sid: str) -> str:
    return hashlib.sha256(sid.strip().encode()).hexdigest()

async def _log(db: AsyncSession, user_id, action: str, entity: str, entity_id: str, detail: dict, request: Request):
    ip = request.client.host if request.client else None
    db.add(AuditLog(user_id=user_id, action=action, entity=entity, entity_id=str(entity_id), detail=detail, ip_address=ip))

# ── Routes ───────────────────────────────────────────────────
@router.post("/send-otp")
async def send_otp(body: SendOtpRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Rate limit: max 5 OTPs per phone per hour (slowapi handles IP; here we check DB)
    recent = await db.scalar(
        select(OtpAttempt).where(
            OtpAttempt.phone == body.phone,
            OtpAttempt.expires_at > datetime.now(timezone.utc)
        )
    )
    if recent and recent.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many OTP requests. Try again later.")

    code      = str(random.randint(100000, 999999))
    code_hash = bcrypt.hash(code)
    expires   = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    otp = OtpAttempt(phone=body.phone, code_hash=code_hash, expires_at=expires)
    db.add(otp)
    await db.flush()

    await send_otp_sms(phone=body.phone, code=code)
    await _log(db, None, "otp_sent", "phone", body.phone, {}, request)

    return {"message": "OTP sent", "expires_in_seconds": settings.OTP_EXPIRE_MINUTES * 60}


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # Find latest valid OTP for this phone
    result = await db.execute(
        select(OtpAttempt)
        .where(OtpAttempt.phone == body.phone, OtpAttempt.expires_at > datetime.now(timezone.utc), OtpAttempt.verified == False)
        .order_by(OtpAttempt.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=400, detail="OTP expired or not found")

    otp.attempts += 1
    if otp.attempts > settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many failed attempts")

    if not bcrypt.verify(body.code, otp.code_hash):
        await db.flush()
        raise HTTPException(status_code=400, detail="Invalid OTP code")

    otp.verified = True

    # Find or create user
    user_result = await db.execute(select(User).where(User.phone == body.phone))
    user = user_result.scalar_one_or_none()
    is_new = user is None

    if is_new:
        if not body.name:
            raise HTTPException(status_code=400, detail="Name required for new users")
        user = User(
            name=body.name,
            phone=body.phone,
            phone_verified=True,
            whatsapp_opt_in=body.whatsapp_opt_in,
            language=body.language,
        )
        db.add(user)
        await db.flush()

    user.phone_verified = True

    # Student discount
    if body.student_id:
        user.student_id_hash = _hash_student_id(body.student_id)
        user.is_student = True
        user.discount_pct = 10.00

    # WhatsApp opt-in
    if body.whatsapp_opt_in and not user.whatsapp_linked:
        user.whatsapp_opt_in = True
        await send_whatsapp_opt_in(user.phone, user.name)

    await db.flush()

    # Issue tokens
    access_token          = _create_access_token(str(user.id))
    raw_refresh, hash_ref = _create_refresh_token()
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_ref,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        device_info=request.headers.get("user-agent", "")[:200],
    )
    db.add(rt)
    await _log(db, user.id, "login" if not is_new else "register", "user", str(user.id), {"is_new": is_new}, request)

    return {
        "access_token":  access_token,
        "refresh_token": raw_refresh,
        "token_type":    "bearer",
        "user": {
            "id":           str(user.id),
            "name":         user.name,
            "phone":        user.phone,
            "is_student":   user.is_student,
            "discount_pct": float(user.discount_pct),
            "language":     user.language,
        },
    }


@router.post("/refresh")
async def refresh_tokens(body: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked == False,
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
    )
    rt = result.scalar_one_or_none()
    if not rt:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    rt.revoked = True  # rotate
    new_access          = _create_access_token(str(rt.user_id))
    raw_refresh, hash_ref = _create_refresh_token()
    new_rt = RefreshToken(
        user_id=rt.user_id,
        token_hash=hash_ref,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        device_info=request.headers.get("user-agent", "")[:200],
    )
    db.add(new_rt)

    return {"access_token": new_access, "refresh_token": raw_refresh, "token_type": "bearer"}


@router.post("/logout")
async def logout(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    rt = result.scalar_one_or_none()
    if rt:
        rt.revoked = True
    return {"message": "Logged out"}


# ── Dependency: current user from JWT ────────────────────────
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

bearer = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
