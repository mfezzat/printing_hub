from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    # App
    SECRET_KEY: str
    DEBUG: bool = False
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # S3 / MinIO
    S3_ENDPOINT: str | None = None
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    S3_REGION: str = "auto"

    # Twilio
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM_WHATSAPP: str | None = None

    # Paymob
    PAYMOB_API_KEY: str | None = None
    PAYMOB_IFRAME_ID: str | None = None
    PAYMOB_HMAC_SECRET: str | None = None
    PAYMOB_INTEGRATION_CARD: str | None = None
    PAYMOB_INTEGRATION_FAWRY: str | None = None
    PAYMOB_INTEGRATION_VODAFONE: str | None = None

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Security
    OTP_EXPIRE_MINUTES: int = 5
    OTP_MAX_ATTEMPTS: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings():
    return Settings()
