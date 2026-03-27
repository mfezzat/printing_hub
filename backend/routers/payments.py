from fastapi import APIRouter, Depends, HTTPException
import httpx
from config import get_settings

from fastapi import APIRouter, Request

router = APIRouter(prefix="/payments", tags=["payments"])

@router.post("/pay")
async def process_payment(request: Request):
    data = await request.json()
    method = data.get("method")
    
    # If customer chooses Vodafone Cash or Fawry
    if method in ["fawry", "vodafone_cash"]:
        return {"status": "pending", "redirect_url": "https://accept.paymob.com/api/..."}
    
    return {"status": "success", "message": "Cash on delivery selected"}

@router.post("/create-intent")
async def create_payment_intent(amount_cents: int, currency: str = "EGP"):
    """
    This starts the Paymob handshake: 
    1. Authenticate 2. Register Order 3. Get Payment Key
    """
    async with httpx.AsyncClient() as client:
        # 1. Get Auth Token
        auth_res = await client.post("https://accept.paymob.com/api/auth/tokens", 
                                    json={"api_key": settings.PAYMOB_API_KEY})
        token = auth_res.json().get("token")

        # 2. Create Order
        order_res = await client.post("https://accept.paymob.com/api/ecommerce/orders", 
            json={
                "auth_token": token,
                "delivery_needed": "false",
                "amount_cents": str(amount_cents),
                "currency": currency,
                "items": []
            })
        order_id = order_res.json().get("id")

        # 3. Get Payment Key (For Credit Card)
        key_res = await client.post("https://accept.paymob.com/api/acceptance/payment_keys",
            json={
                "auth_token": token,
                "amount_cents": str(amount_cents),
                "expiration": 3600,
                "order_id": order_id,
                "billing_data": {
                    "first_name": "Seba", "last_name": "Customer",
                    "email": "test@test.com", "phone_number": "01000000000",
                    "currency": "EGP", "street": "NA", "building": "NA",
                    "floor": "NA", "apartment": "NA", "city": "Obour", "country": "EG"
                },
                "currency": currency,
                "integration_id": settings.PAYMOB_INTEGRATION_CARD
            })
        
        return {"payment_key": key_res.json().get("token")}
