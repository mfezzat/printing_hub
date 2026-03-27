"""
Orders router
  POST   /orders/price-preview   — live price (no DB write)
  POST   /orders                 — create order
  GET    /orders                 — list my orders
  GET    /orders/{id}            — order detail
  PATCH  /orders/{id}/status     — admin: update status
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import uuid

from db import get_db
from models.models import Order, OrderFile, Payment, User
from models.models import OrderTypeEnum, ColorModeEnum, PaymentMethodEnum, PaymentStatusEnum, OrderStatusEnum
from services.pricing import PriceInput, calculate_price
from services.storage import upload_file_chunked
from services.whatsapp import notify_order_status
from routers.auth import get_current_user

router = APIRouter(prefix="/orders", tags=["orders"])


# ── Schemas ──────────────────────────────────────────────────
class PricePreviewRequest(BaseModel):
    paper_type_id:   Optional[int] = None
    gram_option_id:  Optional[int] = None
    texture_id:      Optional[int] = None
    color_mode:      str = "bw"
    copies:          int = 1
    binding_type_id: Optional[int] = None
    page_count:      int = 1

class CreateOrderRequest(BaseModel):
    order_type:      str   # 'print_only' | 'print_bind'
    paper_type_id:   Optional[int] = None
    gram_option_id:  Optional[int] = None
    paper_color_id:  Optional[int] = None
    texture_id:      Optional[int] = None
    color_mode:      str = "bw"
    paper_size:      Optional[str] = None
    copies:          int = 1
    notes:           Optional[str] = None
    binding_type_id: Optional[int] = None
    file_urls:       list[str] = []       # external links
    payment_method:  str = "cod"
    page_count:      int = 1

class StatusUpdateRequest(BaseModel):
    status: str


# ── Price preview (WebSocket-less live update) ────────────────
@router.post("/price-preview")
async def price_preview(
    body: PricePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inp = PriceInput(
        paper_type_id=body.paper_type_id,
        gram_option_id=body.gram_option_id,
        texture_id=body.texture_id,
        color_mode=body.color_mode,
        copies=body.copies,
        binding_type_id=body.binding_type_id,
        discount_pct=float(current_user.discount_pct),
        page_count=body.page_count,
    )
    result = await calculate_price(inp, db)
    return {
        "total":          float(result.total),
        "breakdown":      result.breakdown_lines,
        "discount_pct":   float(current_user.discount_pct),
        "discount_amt":   float(result.discount_amt),
    }


# ── Create order ─────────────────────────────────────────────
@router.post("")
async def create_order(
    body: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    inp = PriceInput(
        paper_type_id=body.paper_type_id,
        gram_option_id=body.gram_option_id,
        texture_id=body.texture_id,
        color_mode=body.color_mode,
        copies=body.copies,
        binding_type_id=body.binding_type_id,
        discount_pct=float(current_user.discount_pct),
        page_count=body.page_count,
    )
    pricing = await calculate_price(inp, db)

    order = Order(
        user_id=current_user.id,
        order_type=body.order_type,
        paper_type_id=body.paper_type_id,
        gram_option_id=body.gram_option_id,
        paper_color_id=body.paper_color_id,
        texture_id=body.texture_id,
        color_mode=body.color_mode,
        paper_size=body.paper_size,
        copies=body.copies,
        notes=body.notes,
        binding_type_id=body.binding_type_id,
        base_price=float(pricing.subtotal),
        discount_amt=float(pricing.discount_amt),
        total_price=float(pricing.total),
        payment_method=body.payment_method,
    )
    db.add(order)
    await db.flush()

    # Save external file links
    for url in body.file_urls:
        db.add(OrderFile(order_id=order.id, file_url=url, upload_status="complete"))

    # Payment record
    payment = Payment(
        order_id=order.id,
        method=body.payment_method,
        gateway="cod" if body.payment_method == "cod" else "paymob",
        amount=float(pricing.total),
    )
    db.add(payment)
    await db.flush()

    # WhatsApp notification
    if current_user.whatsapp_opt_in:
        await notify_order_status(
            phone=current_user.phone,
            name=current_user.name,
            order_id=str(order.id),
            status="pending",
            total=float(pricing.total),
        )

    return {
        "order_id":      str(order.id),
        "status":        "pending",
        "total_price":   float(pricing.total),
        "payment_method": body.payment_method,
        "payment_id":    str(payment.id),
    }


# ── Upload file to an existing order ─────────────────────────
@router.post("/{order_id}/upload")
async def upload_file(
    order_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    storage_key, mime = await upload_file_chunked(file, folder=f"orders/{order_id}")

    of = OrderFile(
        order_id=order.id,
        storage_key=storage_key,
        original_name=file.filename,
        file_size=file.size,
        mime_type=mime,
        upload_status="complete",
    )
    db.add(of)
    return {"file_id": str(of.id), "storage_key": storage_key, "mime_type": mime}


# ── List my orders ────────────────────────────────────────────
@router.get("")
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
        .limit(50)
    )
    orders = result.scalars().all()
    return [
        {
            "id": str(o.id),
            "order_type": o.order_type,
            "status": o.status,
            "total_price": float(o.total_price),
            "created_at": o.created_at.isoformat(),
        }
        for o in orders
    ]


# ── Order detail ──────────────────────────────────────────────
@router.get("/{order_id}")
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    files_result = await db.execute(select(OrderFile).where(OrderFile.order_id == order.id))
    files = files_result.scalars().all()

    return {
        "id":             str(order.id),
        "order_type":     order.order_type,
        "status":         order.status,
        "color_mode":     order.color_mode,
        "paper_size":     order.paper_size,
        "copies":         order.copies,
        "notes":          order.notes,
        "total_price":    float(order.total_price),
        "discount_amt":   float(order.discount_amt),
        "payment_method": order.payment_method,
        "payment_status": order.payment_status,
        "created_at":     order.created_at.isoformat(),
        "files": [
            {"id": str(f.id), "name": f.original_name, "url": f.file_url, "mime": f.mime_type}
            for f in files
        ],
    }


# ── Admin: update status ──────────────────────────────────────
@router.patch("/{order_id}/status")
async def update_status(
    order_id: str,
    body: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    order.status = body.status

    # Notify customer on WhatsApp
    user_result = await db.execute(select(User).where(User.id == order.user_id))
    customer = user_result.scalar_one_or_none()
    if customer and customer.whatsapp_opt_in:
        await notify_order_status(
            phone=customer.phone,
            name=customer.name,
            order_id=order_id,
            status=body.status,
            total=float(order.total_price),
        )

    return {"order_id": order_id, "new_status": body.status}
