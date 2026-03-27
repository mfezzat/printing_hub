-- ============================================================
-- Printing Hub — Complete PostgreSQL Schema
-- Run: psql -U postgres -d printing_hub -f 001_schema.sql
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ────────────────────────────────────────────────────────────
-- USERS
-- ────────────────────────────────────────────────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(120) NOT NULL,
    phone           VARCHAR(20)  NOT NULL UNIQUE,
    phone_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
    whatsapp_opt_in BOOLEAN      NOT NULL DEFAULT FALSE,
    whatsapp_linked BOOLEAN      NOT NULL DEFAULT FALSE,
    student_id_hash VARCHAR(64),                        -- SHA-256 of student ID
    is_student      BOOLEAN      NOT NULL DEFAULT FALSE,
    discount_pct    NUMERIC(5,2) NOT NULL DEFAULT 0,    -- e.g. 10.00
    language        VARCHAR(4)   NOT NULL DEFAULT 'ar', -- 'ar' | 'en'
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_phone ON users(phone);

-- ────────────────────────────────────────────────────────────
-- OTP ATTEMPTS
-- ────────────────────────────────────────────────────────────
CREATE TABLE otp_attempts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone       VARCHAR(20)  NOT NULL,
    code_hash   VARCHAR(64)  NOT NULL,   -- bcrypt hash
    attempts    SMALLINT     NOT NULL DEFAULT 0,
    verified    BOOLEAN      NOT NULL DEFAULT FALSE,
    expires_at  TIMESTAMPTZ  NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_otp_phone ON otp_attempts(phone, expires_at);

-- ────────────────────────────────────────────────────────────
-- REFRESH TOKENS
-- ────────────────────────────────────────────────────────────
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(64) NOT NULL UNIQUE,
    device_info TEXT,
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rt_user ON refresh_tokens(user_id);

-- ────────────────────────────────────────────────────────────
-- CATALOG — PAPER TYPES
-- ────────────────────────────────────────────────────────────
CREATE TABLE paper_types (
    id                   SERIAL PRIMARY KEY,
    name_ar              VARCHAR(60)    NOT NULL,
    name_en              VARCHAR(60)    NOT NULL,
    base_price_multiplier NUMERIC(6,3)  NOT NULL DEFAULT 1.0,
    sort_order           SMALLINT       NOT NULL DEFAULT 0,
    active               BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

INSERT INTO paper_types (name_ar, name_en, base_price_multiplier, sort_order) VALUES
    ('ورق طباعة عادي', 'Plain paper',   1.00, 1),
    ('برستول',          'Bristol',       1.50, 2),
    ('كانسون',          'Canson',        1.80, 3),
    ('كوشيه',           'Coated/Couché', 2.00, 4),
    ('ذبدة',            'Butter paper',  1.60, 5),
    ('كلك',             'Tracing paper', 1.40, 6);

-- ────────────────────────────────────────────────────────────
-- CATALOG — GRAM OPTIONS (per paper type)
-- ────────────────────────────────────────────────────────────
CREATE TABLE gram_options (
    id                SERIAL PRIMARY KEY,
    paper_type_id     INT         NOT NULL REFERENCES paper_types(id),
    grams             SMALLINT    NOT NULL,       -- e.g. 80, 100, 120, 160, 200
    price_multiplier  NUMERIC(5,3) NOT NULL DEFAULT 1.0,
    active            BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO gram_options (paper_type_id, grams, price_multiplier) VALUES
    (1, 80,  1.00), (1, 100, 1.15), (1, 120, 1.30),
    (2, 160, 1.00), (2, 200, 1.20),
    (3, 120, 1.00), (3, 160, 1.20), (3, 200, 1.40),
    (4, 130, 1.00), (4, 170, 1.25),
    (5, 60,  1.00), (5, 80,  1.10),
    (6, 90,  1.00);

-- ────────────────────────────────────────────────────────────
-- CATALOG — PAPER COLORS
-- ────────────────────────────────────────────────────────────
CREATE TABLE paper_colors (
    id        SERIAL PRIMARY KEY,
    name_ar   VARCHAR(40) NOT NULL,
    name_en   VARCHAR(40) NOT NULL,
    hex_code  VARCHAR(7),
    active    BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO paper_colors (name_ar, name_en, hex_code) VALUES
    ('أبيض',  'White',  '#FFFFFF'),
    ('كريمي', 'Cream',  '#FFFDD0'),
    ('أصفر',  'Yellow', '#FFFF99'),
    ('وردي',  'Pink',   '#FFD1DC'),
    ('أزرق',  'Blue',   '#ADD8E6');

-- ────────────────────────────────────────────────────────────
-- CATALOG — TEXTURES
-- ────────────────────────────────────────────────────────────
CREATE TABLE textures (
    id                SERIAL PRIMARY KEY,
    name_ar           VARCHAR(40)  NOT NULL,
    name_en           VARCHAR(40)  NOT NULL,
    price_multiplier  NUMERIC(4,3) NOT NULL DEFAULT 1.0,
    sort_order        SMALLINT     NOT NULL DEFAULT 0,
    active            BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO textures (name_ar, name_en, price_multiplier, sort_order) VALUES
    ('ناعم',  'Smooth',   1.000, 1),
    ('خشن',   'Rough',    1.000, 2),
    ('محبب',  'Grainy',   1.050, 3),
    ('مقلم',  'Lined',    1.050, 4),
    ('قماش',  'Canvas',   1.100, 5);

-- ────────────────────────────────────────────────────────────
-- CATALOG — BINDING TYPES
-- ────────────────────────────────────────────────────────────
CREATE TABLE binding_types (
    id          SERIAL PRIMARY KEY,
    name_ar     VARCHAR(60) NOT NULL,
    name_en     VARCHAR(60) NOT NULL,
    base_price  NUMERIC(8,2) NOT NULL DEFAULT 0,
    active      BOOLEAN      NOT NULL DEFAULT TRUE
);

INSERT INTO binding_types (name_ar, name_en, base_price) VALUES
    ('تجليد سلك مزدوج (Double Wire O)',  'Double wire O-binding', 15.00),
    ('تجليد حرارى',                      'Thermal binding',        12.00),
    ('تدبيس',                            'Stapling',               2.00);

-- ────────────────────────────────────────────────────────────
-- PRICING RULES (admin-editable base prices)
-- ────────────────────────────────────────────────────────────
CREATE TABLE pricing_rules (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(60)  NOT NULL,
    base_price_bw   NUMERIC(8,2) NOT NULL DEFAULT 0.50,  -- per page B&W
    base_price_color NUMERIC(8,2) NOT NULL DEFAULT 2.00, -- per page color
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by      UUID         REFERENCES users(id)
);

INSERT INTO pricing_rules (name, base_price_bw, base_price_color) VALUES
    ('default', 0.50, 2.00);

-- ────────────────────────────────────────────────────────────
-- ORDERS
-- ────────────────────────────────────────────────────────────
CREATE TYPE order_type_enum    AS ENUM ('print_only', 'print_bind');
CREATE TYPE order_status_enum  AS ENUM ('pending', 'confirmed', 'in_progress', 'ready', 'delivered', 'cancelled');
CREATE TYPE color_mode_enum    AS ENUM ('bw', 'color');
CREATE TYPE payment_method_enum AS ENUM ('online', 'cod');
CREATE TYPE payment_status_enum AS ENUM ('pending', 'paid', 'failed', 'refunded');

CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID             NOT NULL REFERENCES users(id),
    order_type      order_type_enum  NOT NULL,
    status          order_status_enum NOT NULL DEFAULT 'pending',

    -- Paper options
    paper_type_id   INT    REFERENCES paper_types(id),
    gram_option_id  INT    REFERENCES gram_options(id),
    paper_color_id  INT    REFERENCES paper_colors(id),
    texture_id      INT    REFERENCES textures(id),
    color_mode      color_mode_enum NOT NULL DEFAULT 'bw',
    paper_size      VARCHAR(20),           -- 'A4', 'A5', 'custom: 10x20cm', ...
    copies          SMALLINT NOT NULL DEFAULT 1,
    notes           TEXT,

    -- Binding (nullable for print_only)
    binding_type_id INT    REFERENCES binding_types(id),

    -- Pricing
    base_price      NUMERIC(10,2) NOT NULL DEFAULT 0,
    discount_amt    NUMERIC(10,2) NOT NULL DEFAULT 0,
    total_price     NUMERIC(10,2) NOT NULL DEFAULT 0,

    -- Payment
    payment_method  payment_method_enum,
    payment_status  payment_status_enum NOT NULL DEFAULT 'pending',

    -- Delivery
    whatsapp_notified BOOLEAN NOT NULL DEFAULT FALSE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user   ON orders(user_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders(status);

-- ────────────────────────────────────────────────────────────
-- ORDER FILES
-- ────────────────────────────────────────────────────────────
CREATE TABLE order_files (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id      UUID        NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    storage_key   TEXT,                    -- S3 key (null if link)
    file_url      TEXT,                    -- external link (null if upload)
    original_name TEXT,
    file_size     BIGINT,
    mime_type     VARCHAR(120),
    upload_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|complete|error
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_files_order ON order_files(order_id);

-- ────────────────────────────────────────────────────────────
-- PAYMENTS (gateway records)
-- ────────────────────────────────────────────────────────────
CREATE TABLE payments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id      UUID                NOT NULL REFERENCES orders(id),
    method        payment_method_enum NOT NULL,
    gateway       VARCHAR(40),                  -- 'paymob', 'fawry', 'vodafone_cash', 'cod'
    gateway_ref   VARCHAR(120),                 -- transaction ID from gateway
    amount        NUMERIC(10,2)       NOT NULL,
    status        payment_status_enum NOT NULL DEFAULT 'pending',
    gateway_data  JSONB,                         -- raw response for reconciliation
    created_at    TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payments_order ON payments(order_id);

-- ────────────────────────────────────────────────────────────
-- WHATSAPP MESSAGES LOG
-- ────────────────────────────────────────────────────────────
CREATE TABLE whatsapp_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID        NOT NULL REFERENCES users(id),
    order_id      UUID        REFERENCES orders(id),
    template_name VARCHAR(80) NOT NULL,
    message_sid   VARCHAR(120),           -- Twilio/Meta message ID
    status        VARCHAR(30),            -- sent | delivered | read | failed
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ────────────────────────────────────────────────────────────
-- AUDIT LOG
-- ────────────────────────────────────────────────────────────
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID,
    action      VARCHAR(80) NOT NULL,
    entity      VARCHAR(40),
    entity_id   TEXT,
    detail      JSONB,
    ip_address  INET,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);

-- ────────────────────────────────────────────────────────────
-- AUTO-UPDATE updated_at trigger
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_upd    BEFORE UPDATE ON users    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_orders_upd   BEFORE UPDATE ON orders   FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_payments_upd BEFORE UPDATE ON payments FOR EACH ROW EXECUTE FUNCTION update_updated_at();
