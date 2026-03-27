import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Numeric, SmallInteger, Integer,
    Text, BigInteger, Enum, ForeignKey, TIMESTAMP, JSON
)
from sqlalchemy.dialects.postgresql import UUID, INET, JSONB
from sqlalchemy.orm import relationship
from db import Base
import enum

# ── Enums ────────────────────────────────────────────────────
class OrderTypeEnum(str, enum.Enum):
    print_only  = "print_only"
    print_bind  = "print_bind"

class OrderStatusEnum(str, enum.Enum):
    pending     = "pending"
    confirmed   = "confirmed"
    in_progress = "in_progress"
    ready       = "ready"
    delivered   = "delivered"
    cancelled   = "cancelled"

class ColorModeEnum(str, enum.Enum):
    bw    = "bw"
    color = "color"

class PaymentMethodEnum(str, enum.Enum):
    online = "online"
    cod    = "cod"

class PaymentStatusEnum(str, enum.Enum):
    pending  = "pending"
    paid     = "paid"
    failed   = "failed"
    refunded = "refunded"

# ── Models ───────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name             = Column(String(120), nullable=False)
    phone            = Column(String(20), nullable=False, unique=True, index=True)
    phone_verified   = Column(Boolean, nullable=False, default=False)
    whatsapp_opt_in  = Column(Boolean, nullable=False, default=False)
    whatsapp_linked  = Column(Boolean, nullable=False, default=False)
    student_id_hash  = Column(String(64))
    is_student       = Column(Boolean, nullable=False, default=False)
    discount_pct     = Column(Numeric(5, 2), nullable=False, default=0)
    language         = Column(String(4), nullable=False, default="ar")
    is_active        = Column(Boolean, nullable=False, default=True)
    created_at       = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at       = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    orders           = relationship("Order", back_populates="user")

class OtpAttempt(Base):
    __tablename__ = "otp_attempts"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone      = Column(String(20), nullable=False, index=True)
    code_hash  = Column(String(64), nullable=False)
    attempts   = Column(SmallInteger, nullable=False, default=0)
    verified   = Column(Boolean, nullable=False, default=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    device_info = Column(Text)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    revoked    = Column(Boolean, nullable=False, default=False)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)

class PaperType(Base):
    __tablename__ = "paper_types"
    id                    = Column(Integer, primary_key=True, autoincrement=True)
    name_ar               = Column(String(60), nullable=False)
    name_en               = Column(String(60), nullable=False)
    base_price_multiplier = Column(Numeric(6, 3), nullable=False, default=1.0)
    sort_order            = Column(SmallInteger, default=0)
    active                = Column(Boolean, nullable=False, default=True)
    created_at            = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    gram_options          = relationship("GramOption", back_populates="paper_type")

class GramOption(Base):
    __tablename__ = "gram_options"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    paper_type_id    = Column(Integer, ForeignKey("paper_types.id"), nullable=False)
    grams            = Column(SmallInteger, nullable=False)
    price_multiplier = Column(Numeric(5, 3), nullable=False, default=1.0)
    active           = Column(Boolean, nullable=False, default=True)
    paper_type       = relationship("PaperType", back_populates="gram_options")

class PaperColor(Base):
    __tablename__ = "paper_colors"
    id       = Column(Integer, primary_key=True, autoincrement=True)
    name_ar  = Column(String(40), nullable=False)
    name_en  = Column(String(40), nullable=False)
    hex_code = Column(String(7))
    active   = Column(Boolean, nullable=False, default=True)

class Texture(Base):
    __tablename__ = "textures"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    name_ar          = Column(String(40), nullable=False)
    name_en          = Column(String(40), nullable=False)
    price_multiplier = Column(Numeric(4, 3), nullable=False, default=1.0)
    sort_order       = Column(SmallInteger, default=0)
    active           = Column(Boolean, nullable=False, default=True)

class BindingType(Base):
    __tablename__ = "binding_types"
    id         = Column(Integer, primary_key=True, autoincrement=True)
    name_ar    = Column(String(60), nullable=False)
    name_en    = Column(String(60), nullable=False)
    base_price = Column(Numeric(8, 2), nullable=False, default=0)
    active     = Column(Boolean, nullable=False, default=True)

class PricingRule(Base):
    __tablename__ = "pricing_rules"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    name              = Column(String(60), nullable=False)
    base_price_bw     = Column(Numeric(8, 2), nullable=False, default=0.50)
    base_price_color  = Column(Numeric(8, 2), nullable=False, default=2.00)
    updated_at        = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by        = Column(UUID(as_uuid=True), ForeignKey("users.id"))

class Order(Base):
    __tablename__ = "orders"
    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_type       = Column(Enum(OrderTypeEnum), nullable=False)
    status           = Column(Enum(OrderStatusEnum), nullable=False, default=OrderStatusEnum.pending)
    paper_type_id    = Column(Integer, ForeignKey("paper_types.id"))
    gram_option_id   = Column(Integer, ForeignKey("gram_options.id"))
    paper_color_id   = Column(Integer, ForeignKey("paper_colors.id"))
    texture_id       = Column(Integer, ForeignKey("textures.id"))
    color_mode       = Column(Enum(ColorModeEnum), nullable=False, default=ColorModeEnum.bw)
    paper_size       = Column(String(20))
    copies           = Column(SmallInteger, nullable=False, default=1)
    notes            = Column(Text)
    binding_type_id  = Column(Integer, ForeignKey("binding_types.id"))
    base_price       = Column(Numeric(10, 2), nullable=False, default=0)
    discount_amt     = Column(Numeric(10, 2), nullable=False, default=0)
    total_price      = Column(Numeric(10, 2), nullable=False, default=0)
    payment_method   = Column(Enum(PaymentMethodEnum))
    payment_status   = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.pending)
    whatsapp_notified = Column(Boolean, nullable=False, default=False)
    created_at       = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at       = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    user             = relationship("User", back_populates="orders")
    files            = relationship("OrderFile", back_populates="order")
    payments         = relationship("Payment", back_populates="order")

class OrderFile(Base):
    __tablename__ = "order_files"
    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id      = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    storage_key   = Column(Text)
    file_url      = Column(Text)
    original_name = Column(Text)
    file_size     = Column(BigInteger)
    mime_type     = Column(String(120))
    upload_status = Column(String(20), nullable=False, default="pending")
    created_at    = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    order         = relationship("Order", back_populates="files")

class Payment(Base):
    __tablename__ = "payments"
    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id     = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    method       = Column(Enum(PaymentMethodEnum), nullable=False)
    gateway      = Column(String(40))
    gateway_ref  = Column(String(120))
    amount       = Column(Numeric(10, 2), nullable=False)
    status       = Column(Enum(PaymentStatusEnum), nullable=False, default=PaymentStatusEnum.pending)
    gateway_data = Column(JSONB)
    created_at   = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
    updated_at   = Column(TIMESTAMP(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    order        = relationship("Order", back_populates="payments")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id         = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id    = Column(UUID(as_uuid=True))
    action     = Column(String(80), nullable=False)
    entity     = Column(String(40))
    entity_id  = Column(Text)
    detail     = Column(JSONB)
    ip_address = Column(INET)
    created_at = Column(TIMESTAMP(timezone=True), default=datetime.utcnow)
