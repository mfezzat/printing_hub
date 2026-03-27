"""
Payments router — Paymob integration for Egypt.
Supports: Visa/MC, Fawry, Vodafone Cash, InstaPay, and COD.

Flow:
  1. POST /payments/initiate  → get Paymob payment token + iframe URL
  2. Paymob calls  /payments/callback (webhook) → update order status
  3. GET  /payments/{order_id} → check current payment status
"""
import hashlib, hmac
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from pydantic import BaseModel
from typing import Optional

from db import get_db
from config import get_settings
from models.models import Order, Payment, User, PaymentStatusEnum, OrderStatusEnum
from routers.auth import get_current_user

router   = APIRouter(prefix="/payments", tags=["payments"])
settings = get_settings()

PAYMOB_BASE = "https://accept.paymob.com/api"


class InitiatePaymentRequest(BaseModel):
    order_id:     str
    gateway:      str = "card"   # 'card' | 'fawry' | 'vodafone_cash'


# ── Step 1: Authenticate with Paymob ─────────────────────────
async def _paymob_auth_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(f"{PAYMOB_BASE}/auth/tokens", json={"api_key": settings.PAYMOB_API_KEY})
    resp.raise_for_status()
    return resp.json()["token"]


# ── Step 2: Register order with Paymob ───────────────────────
async def _register_order(client, auth_token: str, amount_cents: int, order_id: str) -> str:
    resp = await client.post(f"{PAYMOB_BASE}/ecommerce/orders", json={
        "auth_token":        auth_token,
        "delivery_needed":   False,
        "amount_cents":      amount_cents,
        "currency":          "EGP",
        "merchant_order_id": order_id,
        "items":             [],
    })
    resp.raise_for_status()
    return str(resp.json()["id"])


# ── Step 3: Get payment key ───────────────────────────────────
async def _get_payment_key(client, auth_token, paymob_order_id, amount_cents, integration_id, user, order_id) -> str:
    resp = await client.post(f"{PAYMOB_BASE}/acceptance/payment_keys", json={
        "auth_token":     auth_token,
        "amount_cents":   amount_cents,
        "expiration":     3600,
        "order_id":       paymob_order_id,
        "integration_id": integration_id,
        "currency":       "EGP",
        "billing_data": {
            "first_name":   user.name.split()[0],
            "last_name":    user.name.split()[-1] if len(user.name.split()) > 1 else ".",
            "phone_number": user.phone,
            "email":        f"{user.phone.replace('+', '')}@printinghub.app",
            "apartment":    "NA", "floor": "NA", "street": "NA",
            "building":     "NA", "city":  "Cairo", "country": "EG",
            "postal_code":  "NA", "state": "Cairo",
        },
        "lock_order_when_paid": True,
    })
    resp.raise_for_status()
    return resp.json()["token"]


# ── Integration ID selector ───────────────────────────────────
def _integration_id(gateway: str) -> str:
    mapping = {
        "card":          settings.PAYMOB_INTEGRATION_CARD,
        "fawry":         settings.PAYMOB_INTEGRATION_FAWRY,
        "vodafone_cash": settings.PAYMOB_INTEGRATION_VODAFONE,
    }
    iid = mapping.get(gateway)
    if not iid:
        raise HTTPException(status_code=400, detail=f"Unsupported gateway: {gateway}")
    return iid


# ── Initiate payment ──────────────────────────────────────────
@router.post("/initiate")
async def initiate_payment(
    body: InitiatePaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == body.order_id, Order.user_id == current_user.id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.payment_status == PaymentStatusEnum.paid:
        raise HTTPException(status_code=400, detail="Order already paid")

    amount_cents = int(float(order.total_price) * 100)
    integration_id = _integration_id(body.gateway)

    async with httpx.AsyncClient(timeout=30) as client:
        auth_token      = await _paymob_auth_token(client)
        paymob_order_id = await _register_order(client, auth_token, amount_cents, str(order.id))
        payment_key     = await _get_payment_key(client, auth_token, paymob_order_id, amount_cents, integration_id, current_user, str(order.id))

    # Save payment record
    pay_result = await db.execute(select(Payment).where(Payment.order_id == order.id))
    payment = pay_result.scalar_one_or_none()
    if payment:
        payment.gateway     = body.gateway
        payment.gateway_ref = paymob_order_id
    else:
        payment = Payment(order_id=order.id, method="online", gateway=body.gateway, gateway_ref=paymob_order_id, amount=float(order.total_price))
        db.add(payment)

    iframe_url = f"https://accept.paymob.com/api/acceptance/iframes/{settings.PAYMOB_IFRAME_ID}?payment_token={payment_key}"

    return {
        "iframe_url":    iframe_url,
        "payment_key":   payment_key,
        "amount_cents":  amount_cents,
        "gateway":       body.gateway,
    }


# ── Paymob webhook callback ───────────────────────────────────
@router.post("/callback")
async def paymob_callback(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()

    # Verify HMAC
    obj = data.get("obj", {})
    hmac_fields = [
        str(obj.get("amount_cents", "")), str(obj.get("created_at", "")),
        str(obj.get("currency", "")), str(obj.get("error_occured", "")),
        str(obj.get("has_parent_transaction", "")), str(obj.get("id", "")),
        str(obj.get("integration_id", "")), str(obj.get("is_3d_secure", "")),
        str(obj.get("is_auth", "")), str(obj.get("is_capture", "")),
        str(obj.get("is_refunded", "")), str(obj.get("is_standalone_payment", "")),
        str(obj.get("is_voided", "")), str(obj.get("order", {}).get("id", "")),
        str(obj.get("owner", "")), str(obj.get("pending", "")),
        str(obj.get("source_data", {}).get("pan", "")),
        str(obj.get("source_data", {}).get("sub_type", "")),
        str(obj.get("source_data", {}).get("type", "")),
        str(obj.get("success", "")),
    ]
    message   = "".join(hmac_fields)
    computed  = hmac.new(settings.PAYMOB_HMAC_SECRET.encode(), message.encode(), hashlib.sha512).hexdigest()
    received  = request.query_params.get("hmac", "")
    if not hmac.compare_digest(computed, received):
        raise HTTPException(status_code=400, detail="Invalid HMAC")

    success       = obj.get("success") == True
    merchant_ref  = obj.get("order", {}).get("merchant_order_id")
    if not merchant_ref:
        return {"received": True}

    result = await db.execute(select(Order).where(Order.id == merchant_ref))
    order  = result.scalar_one_or_none()
    if not order:
        return {"received": True}

    if success:
        order.payment_status = PaymentStatusEnum.paid
        order.status         = OrderStatusEnum.confirmed
    else:
        order.payment_status = PaymentStatusEnum.failed

    return {"received": True}


# ── Check payment status ──────────────────────────────────────
@router.get("/{order_id}")
async def payment_status(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id, Order.user_id == current_user.id))
    order  = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "payment_status": order.payment_status, "order_status": order.status}
