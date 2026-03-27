# Printing Hub — Complete Setup Guide

## Project structure

```
printing_hub/
├── backend/
│   ├── main.py                  FastAPI application entry point
│   ├── config.py                Settings (reads .env)
│   ├── db.py                    PostgreSQL async connection pool
│   ├── requirements.txt         Python dependencies
│   ├── Dockerfile
│   ├── migrations/
│   │   └── 001_schema.sql       Full database schema — run this first
│   ├── models/
│   │   └── models.py            SQLAlchemy ORM models
│   ├── routers/
│   │   ├── auth.py              Phone OTP, JWT, registration
│   │   ├── orders.py            Create/list orders, live price preview
│   │   ├── catalog.py           Paper types, gram options, textures
│   │   └── payments.py          Paymob online + COD flow
│   └── services/
│       ├── pricing.py           Live price calculation engine
│       ├── whatsapp.py          Twilio WhatsApp notifications
│       ├── sms.py               OTP via SMS
│       └── storage.py           S3-compatible chunked file upload
├── frontend/
│   ├── index.html               Complete PWA — all screens, Arabic + English
│   └── public/
│       ├── manifest.json        PWA manifest
│       └── sw.js                Service worker (offline support)
├── admin/
│   └── admin.html               Full admin panel (Windows desktop web app)
├── docker-compose.yml           Full stack: DB + Redis + MinIO + Backend + Nginx
├── nginx.conf                   Reverse proxy + SSL + file upload config
└── .env.template                Copy to .env and fill in credentials
```

---

## Quick start (Docker)

### 1. Prerequisites
- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- A domain name with SSL certificate (Let's Encrypt is free)

### 2. Configure environment
```bash
cp .env.template .env
# Edit .env with your values (see Configuration section below)
```

### 3. Create the database
```bash
docker compose up db -d
docker compose exec db psql -U ph_user -d printing_hub -f /docker-entrypoint-initdb.d/001_schema.sql
```

### 4. Start everything
```bash
docker compose up -d
```

The app is now running at:
- **Customer app (PWA):** https://yourdomain.com
- **Admin panel:** https://yourdomain.com/admin/ (local network only)
- **API docs:** https://yourdomain.com/api/docs (DEBUG=true only)

---

## Configuration

### Required credentials

| Service | Where to get | Used for |
|---------|-------------|----------|
| Twilio | twilio.com | SMS OTP + WhatsApp |
| Paymob | accept.paymob.com | Online payments (Egypt) |
| MinIO | Self-hosted (included in docker-compose) | File storage |

### Twilio setup (WhatsApp)
1. Create a Twilio account at twilio.com
2. Enable the WhatsApp Sandbox or apply for a production number
3. Get your Account SID and Auth Token from the Twilio Console
4. Fill in `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_WHATSAPP`

### Paymob setup (Egypt)
1. Register at accept.paymob.com
2. Create integrations for: Card, Fawry, Vodafone Cash
3. Note each integration ID and your iframe ID
4. Fill in all `PAYMOB_*` values in .env

### MinIO (file storage, self-hosted)
MinIO runs automatically via docker-compose. Access the console at port 9001:
- Create the bucket named `printing-hub-files`
- Set the bucket policy to allow the backend to upload/download

---

## Running without Docker (development)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.template ../.env
# Edit .env
uvicorn main:app --reload --port 8000
```

### Frontend (PWA)
The `frontend/index.html` is a single-file PWA. During development serve it with any static server:
```bash
# Python
python -m http.server 3000 --directory frontend
# Or Node
npx serve frontend -p 3000
```

### Admin panel
Open `admin/admin.html` directly in a browser (no server needed in dev), or serve:
```bash
python -m http.server 3001 --directory admin
```

---

## API reference

All endpoints are prefixed with `/api/v1`.

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/send-otp` | Send OTP to phone number |
| POST | `/auth/verify-otp` | Verify OTP, register/login, get JWT |
| POST | `/auth/refresh` | Rotate refresh token |
| POST | `/auth/logout` | Revoke refresh token |

### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders/price-preview` | Live price calculation (no DB write) |
| POST | `/orders` | Create new order |
| POST | `/orders/{id}/upload` | Upload file to order |
| GET | `/orders` | List my orders |
| GET | `/orders/{id}` | Order detail |
| PATCH | `/orders/{id}/status` | Update order status (admin) |

### Catalog (no auth required)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/catalog/paper-types` | List paper types |
| GET | `/catalog/gram-options/{paper_type_id}` | Gram options for a paper type |
| GET | `/catalog/textures` | List textures |
| GET | `/catalog/binding-types` | List binding types |
| GET | `/catalog/pricing-rules` | Current base prices |

### Payments
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/payments/initiate` | Get Paymob iframe URL |
| POST | `/payments/callback` | Paymob webhook (HMAC verified) |
| GET | `/payments/{order_id}` | Check payment status |

---

## Security checklist

- [x] OTP codes bcrypt-hashed, expire in 5 minutes
- [x] JWT access tokens expire in 1 hour
- [x] Refresh tokens rotated on each use
- [x] File MIME types validated server-side before storage
- [x] All API endpoints rate-limited via slowapi
- [x] Student IDs stored as SHA-256 hashes only
- [x] HTTPS enforced via Nginx with HSTS
- [x] Admin panel restricted to local network (192.168.x.x / 10.x.x.x)
- [x] Security headers on all responses
- [x] Paymob webhook HMAC verified
- [x] File uploads streamed (no size limit, no memory pressure)
- [x] No passwords stored — phone OTP only

---

## Website integration

To connect Printing Hub to your existing website, add this to your website's backend:

```python
# Shared JWT secret allows users logged in on the website
# to skip re-registration in the Printing Hub app.

import httpx

async def get_printing_hub_token(user_phone: str, user_name: str) -> str:
    """Exchange website session for Printing Hub JWT."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://yourdomain.com/api/v1/auth/website-bridge",
            headers={"X-API-Key": WEBSITE_API_KEY},
            json={"phone": user_phone, "name": user_name}
        )
        return resp.json()["access_token"]
```

---

## Admin panel features

Open `https://yourdomain.com/admin/` from any Windows/Mac browser on your local network.

- **Dashboard** — today's orders, pending count, weekly chart, revenue
- **Orders** — filter by status, update status inline, send WhatsApp update
- **Customers** — view all registered users, student status, WhatsApp opt-in
- **Paper types** — add/edit/disable paper types and gram options
- **Textures & colors** — add/edit/disable textures
- **Binding types** — add/edit/disable binding options
- **Pricing** — change base price per page (B&W and color), live preview
- **Settings** — WhatsApp toggle, order acceptance toggle, maintenance mode

All catalog changes (new paper types, textures, binding types) take effect in the customer app immediately without any code change or restart.
