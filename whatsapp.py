"""services/whatsapp.py — Twilio WhatsApp integration"""
import httpx
from config import get_settings

settings = get_settings()

STATUS_MESSAGES = {
    "pending":     {"ar": "تم استلام طلبك رقم {id} بنجاح. إجمالي الطلب: {total} ج.م",
                    "en": "Your order #{id} received. Total: EGP {total}"},
    "confirmed":   {"ar": "تم تأكيد طلبك رقم {id} وبدأ العمل عليه.",
                    "en": "Order #{id} confirmed and in queue."},
    "in_progress": {"ar": "طلبك رقم {id} قيد الطباعة الآن.",
                    "en": "Order #{id} is being printed now."},
    "ready":       {"ar": "طلبك رقم {id} جاهز للاستلام!",
                    "en": "Order #{id} is ready for pickup!"},
    "delivered":   {"ar": "شكراً! تم تسليم طلبك رقم {id}. نراك قريباً.",
                    "en": "Thank you! Order #{id} delivered. See you soon."},
    "cancelled":   {"ar": "تم إلغاء طلبك رقم {id}. تواصل معنا لأي استفسار.",
                    "en": "Order #{id} cancelled. Contact us for questions."},
}


async def send_whatsapp_opt_in(phone: str, name: str):
    """Send the initial opt-in message after registration."""
    if not settings.TWILIO_ACCOUNT_SID:
        return  # skip in dev
    body = f"مرحباً {name}! تم ربط رقمك بـ Printing Hub. ستصلك تحديثات طلباتك هنا مباشرة."
    await _send(phone, body)


async def notify_order_status(phone: str, name: str, order_id: str, status: str, total: float):
    """Send order status update."""
    if not settings.TWILIO_ACCOUNT_SID:
        return
    short_id = order_id[:8].upper()
    tmpl = STATUS_MESSAGES.get(status, {})
    body = tmpl.get("ar", f"تحديث طلبك {short_id}").format(id=short_id, total=f"{total:.2f}")
    await _send(phone, body)


async def _send(phone: str, body: str):
    url  = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    data = {
        "From": settings.TWILIO_FROM_WHATSAPP,
        "To":   f"whatsapp:{phone}",
        "Body": body,
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, data=data, auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN))
