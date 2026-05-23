-- Intentional schema drift for demo — sentinels detect these on first scan

-- DRIFT 1: Change total_amount from NUMERIC to VARCHAR (type change = critical)
ALTER TABLE public.orders ALTER COLUMN total_amount TYPE VARCHAR(50) USING total_amount::text;

-- DRIFT 2: Add a new column to orders (column addition)
ALTER TABLE public.orders ADD COLUMN discount_code VARCHAR(30);

-- DRIFT 3: Drop the method column from stg_payments (column deletion = critical)
ALTER TABLE staging.stg_payments DROP COLUMN method;

-- DRIFT 4: Change email type from VARCHAR to TEXT in customers (type change = critical)
ALTER TABLE public.customers ALTER COLUMN email TYPE TEXT;

-- DRIFT 5: Drop unit_price from order_items (column deletion = critical)
ALTER TABLE public.order_items DROP COLUMN unit_price;

-- DRIFT 6: Add unexpected columns to raw_events (column addition)
ALTER TABLE raw.raw_events ADD COLUMN pii_name VARCHAR(200);
ALTER TABLE raw.raw_events ADD COLUMN pii_ssn VARCHAR(11);

-- DRIFT 7: Change total_revenue from NUMERIC to INTEGER in daily_revenue (type change = critical, loses precision)
ALTER TABLE analytics.daily_revenue ALTER COLUMN total_revenue TYPE INTEGER USING total_revenue::integer;

-- DRIFT 8: Make daily_revenue even more stale (update old timestamps further back)
UPDATE analytics.daily_revenue SET updated_at = now() - interval '5 days';
