-- =============================================================
-- Aegis Data Intelligence Platform — Bootstrap Schema
-- Runs once via docker-entrypoint-initdb.d on first Postgres boot
-- =============================================================

-- -----------------------------------------------
-- 1. Create schemas
-- -----------------------------------------------
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS raw;

-- -----------------------------------------------
-- 2. Tables
-- -----------------------------------------------

-- public.customers
CREATE TABLE public.customers (
    id          SERIAL PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    tier        VARCHAR(20)  NOT NULL DEFAULT 'standard',
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- public.products
CREATE TABLE public.products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,
    price       NUMERIC(10,2) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- public.orders
CREATE TABLE public.orders (
    id            SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES public.customers(id),
    total_amount  NUMERIC(10,2) NOT NULL,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

-- public.order_items
CREATE TABLE public.order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER NOT NULL REFERENCES public.orders(id),
    product_id  INTEGER NOT NULL REFERENCES public.products(id),
    quantity    INTEGER NOT NULL DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- staging.stg_payments
CREATE TABLE staging.stg_payments (
    payment_id   SERIAL PRIMARY KEY,
    order_id     INTEGER NOT NULL,
    amount       NUMERIC(10,2) NOT NULL,
    method       VARCHAR(20) NOT NULL,
    processed_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at   TIMESTAMP NOT NULL DEFAULT now()
);

-- staging.stg_shipments
CREATE TABLE staging.stg_shipments (
    shipment_id     SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL,
    carrier         VARCHAR(50) NOT NULL,
    tracking_number VARCHAR(100) NOT NULL,
    shipped_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- raw.raw_events
CREATE TABLE raw.raw_events (
    id          SERIAL PRIMARY KEY,
    event_type  VARCHAR(50) NOT NULL,
    payload     JSONB NOT NULL DEFAULT '{}'::jsonb,
    received_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- raw.raw_clickstream
CREATE TABLE raw.raw_clickstream (
    id          SERIAL PRIMARY KEY,
    session_id  VARCHAR(64) NOT NULL,
    page_url    VARCHAR(500) NOT NULL,
    action      VARCHAR(30) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT now(),
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- analytics.daily_revenue
CREATE TABLE analytics.daily_revenue (
    id              SERIAL PRIMARY KEY,
    report_date     DATE NOT NULL,
    total_revenue   NUMERIC(12,2) NOT NULL,
    order_count     INTEGER NOT NULL,
    avg_order_value NUMERIC(10,2) NOT NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT now(),
    updated_at      TIMESTAMP NOT NULL DEFAULT now()
);

-- analytics.customer_ltv
CREATE TABLE analytics.customer_ltv (
    id             SERIAL PRIMARY KEY,
    customer_id    INTEGER NOT NULL,
    total_spend    NUMERIC(12,2) NOT NULL,
    order_count    INTEGER NOT NULL DEFAULT 0,
    first_order_at TIMESTAMP,
    last_order_at  TIMESTAMP,
    tier           VARCHAR(20) NOT NULL DEFAULT 'standard',
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);

-- -----------------------------------------------
-- 3. Demo data
-- -----------------------------------------------

-- 5 customers
INSERT INTO public.customers (email, name, tier) VALUES
    ('alice@example.com',   'Alice Johnson',  'premium'),
    ('bob@example.com',     'Bob Smith',      'standard'),
    ('carol@example.com',   'Carol Lee',      'enterprise'),
    ('dave@example.com',    'Dave Kim',       'standard'),
    ('eve@example.com',     'Eve Martinez',   'premium');

-- 5 products
INSERT INTO public.products (name, category, price) VALUES
    ('Wireless Mouse',       'electronics', 29.99),
    ('Mechanical Keyboard',  'electronics', 89.99),
    ('Standing Desk',        'furniture',  349.99),
    ('Monitor Arm',          'furniture',   54.99),
    ('USB-C Hub',            'electronics', 39.99);

-- 6 orders
INSERT INTO public.orders (customer_id, total_amount, status) VALUES
    (1, 119.98, 'completed'),
    (2,  89.99, 'completed'),
    (3, 404.98, 'completed'),
    (1,  39.99, 'shipped'),
    (4,  29.99, 'pending'),
    (5, 144.98, 'completed');

-- 11 order_items
INSERT INTO public.order_items (order_id, product_id, quantity, unit_price) VALUES
    (1, 1, 1, 29.99),
    (1, 2, 1, 89.99),
    (2, 2, 1, 89.99),
    (3, 3, 1, 349.99),
    (3, 4, 1, 54.99),
    (4, 5, 1, 39.99),
    (5, 1, 1, 29.99),
    (6, 2, 1, 89.99),
    (6, 4, 1, 54.99),
    (6, 1, 1, 29.99),
    (3, 5, 1, 39.99);

-- 5 stg_payments
INSERT INTO staging.stg_payments (order_id, amount, method) VALUES
    (1, 119.98, 'credit_card'),
    (2,  89.99, 'paypal'),
    (3, 404.98, 'credit_card'),
    (4,  39.99, 'debit_card'),
    (6, 144.98, 'credit_card');

-- 4 stg_shipments
INSERT INTO staging.stg_shipments (order_id, carrier, tracking_number) VALUES
    (1, 'UPS',   '1Z999AA10123456784'),
    (2, 'FedEx', '794644790132'),
    (3, 'USPS',  '9400111899223033005282'),
    (4, 'UPS',   '1Z999AA10123456799');

-- 5 raw_events
INSERT INTO raw.raw_events (event_type, payload) VALUES
    ('page_view',    '{"url": "/products", "user_id": 1}'),
    ('add_to_cart',  '{"product_id": 2, "quantity": 1}'),
    ('checkout',     '{"order_id": 1, "total": 119.98}'),
    ('page_view',    '{"url": "/", "user_id": 3}'),
    ('signup',       '{"email": "newuser@example.com"}');

-- 5 raw_clickstream
INSERT INTO raw.raw_clickstream (session_id, page_url, action) VALUES
    ('sess_abc123', '/products',       'click'),
    ('sess_abc123', '/products/2',     'click'),
    ('sess_abc123', '/cart',           'click'),
    ('sess_def456', '/',               'pageview'),
    ('sess_def456', '/products',       'scroll');

-- 3 daily_revenue rows — intentionally stale updated_at for freshness sentinel
INSERT INTO analytics.daily_revenue (report_date, total_revenue, order_count, avg_order_value, created_at, updated_at) VALUES
    (CURRENT_DATE - INTERVAL '3 days', 209.97, 2, 104.99, now() - INTERVAL '3 days', now() - INTERVAL '3 days'),
    (CURRENT_DATE - INTERVAL '2 days', 404.98, 1, 404.98, now() - INTERVAL '2 days', now() - INTERVAL '2 days'),
    (CURRENT_DATE - INTERVAL '1 day',  184.97, 3, 61.66,  now() - INTERVAL '1 day',  now() - INTERVAL '1 day');

-- 4 customer_ltv
INSERT INTO analytics.customer_ltv (customer_id, total_spend, order_count, first_order_at, last_order_at, tier) VALUES
    (1, 159.97, 2, now() - INTERVAL '30 days', now() - INTERVAL '1 day',  'premium'),
    (2,  89.99, 1, now() - INTERVAL '20 days', now() - INTERVAL '20 days','standard'),
    (3, 404.98, 1, now() - INTERVAL '10 days', now() - INTERVAL '10 days','enterprise'),
    (5, 144.98, 1, now() - INTERVAL '5 days',  now() - INTERVAL '5 days', 'premium');
