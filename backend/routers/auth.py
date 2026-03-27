from datetime import datetime, timedelta, timezone
import hashlib, secrets, random
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from jose import jwt
from passlib.hash import bcrypt

from db import get_db
from config import get_settings
from models.models import User, OtpAttempt

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

class VerifyOtpRequest(BaseModel):
    phone: str
    code: str
    name: str | None = None
    whatsapp_opt_in: bool = False
    language: str = "ar"

def _create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest, request: Request, db: AsyncSession = Depends(get_db)):
    # --- TEST BYPASS (Active only when DEBUG=true in .env) ---
    if settings.DEBUG and body.code == "123456":
        result = await db.execute(select(User).where(User.phone == body.phone))
        user = result.scalar_one_or_none()
        
        if not user:
            if not body.name:
                raise HTTPException(status_code=400, detail="Name required for new users")
            user = User(name=body.name, phone=body.phone, phone_verified=True, language=body.language)
            db.add(user)
            await db.flush()
        
        access_token = _create_access_token(str(user.id))
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "name": user.name,
                "phone": user.phone,
                "language": user.language
            }
        }

    # Standard Production Logic
    result = await db.execute(
        select(OtpAttempt)
        .where(OtpAttempt.phone == body.phone, OtpAttempt.verified == False)
        .order_by(OtpAttempt.created_at.desc())
    )
    otp = result.scalar_one_or_none()
    
    if not otp or not bcrypt.verify(body.code, otp.code_hash):
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    
    # Issue real tokens here...
    return {"message": "Success"}