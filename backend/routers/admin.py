from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from db import get_db
from models.models import PricingConfig
from pydantic import BaseModel

router = APIRouter(prefix="/admin/pricing", tags=["admin"])

class PriceUpdate(BaseModel):
    category: str
    price: float

@router.get("")
async def list_prices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PricingConfig))
    return result.scalars().all()

@router.post("/update")
async def update_pricing(data: PriceUpdate, db: AsyncSession = Depends(get_db)):
    # This logic allows you to change 80gsm vs 100gsm prices from the GUI
    query = update(PricingConfig).where(PricingConfig.category == data.category).values(price_per_unit=data.price)
    await db.execute(query)
    await db.commit()
    return {"status": "success", "updated": data.category}