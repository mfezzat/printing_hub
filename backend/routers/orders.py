from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_db
from models.models import PricingConfig # Ensure this import is correct

router = APIRouter(prefix="/orders", tags=["orders"])

@router.post("/price-preview")
async def price_preview(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    gsm_type = f"paper_{data.get('gsm', 80)}gsm"
    
    # Corrected Query (No stray 'y'!)
    result = await db.execute(select(PricingConfig).where(PricingConfig.category == gsm_type))
    config = result.scalars().first()
    
    # Fallback price if DB is empty
    base_price = config.price_per_unit if config else 45.0
    qty = int(data.get("quantity", 1))
    
    total = base_price * qty # Simplified for testing
    return {"subtotal": total, "tax": total * 0.14, "total": total * 1.14}