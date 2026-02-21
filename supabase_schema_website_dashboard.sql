-- Website Dashboard split schema
-- NOTE: This file is intentionally separate from existing supabase_schema.sql

-- 1) Product-level website-only description
ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS website_description TEXT;

-- 2) Website users (mapped from Supabase Auth users)
CREATE TABLE IF NOT EXISTS public.website_users (
  id BIGSERIAL PRIMARY KEY,
  auth_user_id UUID NOT NULL UNIQUE,
  email TEXT NOT NULL,
  display_name TEXT,
  last_sign_in_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_website_users_email_lower
  ON public.website_users (LOWER(email));

CREATE INDEX IF NOT EXISTS idx_website_users_auth_user_id
  ON public.website_users (auth_user_id);

-- 3) Website direct orders (separate from bot direct_orders)
CREATE TABLE IF NOT EXISTS public.website_direct_orders (
  id BIGSERIAL PRIMARY KEY,
  auth_user_id UUID,
  user_email TEXT,
  product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  quantity INTEGER NOT NULL DEFAULT 1,
  bonus_quantity INTEGER NOT NULL DEFAULT 0,
  unit_price BIGINT NOT NULL DEFAULT 0,
  amount BIGINT NOT NULL DEFAULT 0,
  code TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'failed', 'cancelled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ,
  fulfilled_order_id BIGINT
);

CREATE INDEX IF NOT EXISTS idx_website_direct_orders_auth_user_id
  ON public.website_direct_orders (auth_user_id);

CREATE INDEX IF NOT EXISTS idx_website_direct_orders_status_created_at
  ON public.website_direct_orders (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_website_direct_orders_product_id
  ON public.website_direct_orders (product_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'website_direct_orders_auth_user_id_fkey'
  ) THEN
    ALTER TABLE public.website_direct_orders
      ADD CONSTRAINT website_direct_orders_auth_user_id_fkey
      FOREIGN KEY (auth_user_id)
      REFERENCES public.website_users(auth_user_id)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
  END IF;
END $$;

-- 4) Website delivered orders (separate from bot orders)
CREATE TABLE IF NOT EXISTS public.website_orders (
  id BIGSERIAL PRIMARY KEY,
  auth_user_id UUID,
  user_email TEXT,
  product_id BIGINT NOT NULL REFERENCES public.products(id) ON UPDATE CASCADE ON DELETE RESTRICT,
  content TEXT,
  price BIGINT NOT NULL DEFAULT 0,
  quantity INTEGER NOT NULL DEFAULT 1,
  order_group TEXT,
  source_direct_code TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_website_orders_auth_user_id
  ON public.website_orders (auth_user_id);

CREATE INDEX IF NOT EXISTS idx_website_orders_created_at
  ON public.website_orders (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_website_orders_product_id
  ON public.website_orders (product_id);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'website_orders_auth_user_id_fkey'
  ) THEN
    ALTER TABLE public.website_orders
      ADD CONSTRAINT website_orders_auth_user_id_fkey
      FOREIGN KEY (auth_user_id)
      REFERENCES public.website_users(auth_user_id)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
  END IF;
END $$;

-- Link website_direct_orders.fulfilled_order_id -> website_orders.id
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'website_direct_orders_fulfilled_order_id_fkey'
  ) THEN
    ALTER TABLE public.website_direct_orders
      ADD CONSTRAINT website_direct_orders_fulfilled_order_id_fkey
      FOREIGN KEY (fulfilled_order_id)
      REFERENCES public.website_orders(id)
      ON UPDATE CASCADE
      ON DELETE SET NULL;
  END IF;
END $$;

-- 5) Generic updated_at trigger helper
CREATE OR REPLACE FUNCTION public.set_row_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_website_users_updated_at ON public.website_users;
CREATE TRIGGER trg_website_users_updated_at
BEFORE UPDATE ON public.website_users
FOR EACH ROW
EXECUTE FUNCTION public.set_row_updated_at();

DROP TRIGGER IF EXISTS trg_website_direct_orders_updated_at ON public.website_direct_orders;
CREATE TRIGGER trg_website_direct_orders_updated_at
BEFORE UPDATE ON public.website_direct_orders
FOR EACH ROW
EXECUTE FUNCTION public.set_row_updated_at();

-- 6) Backfill website_users from auth.users
INSERT INTO public.website_users (auth_user_id, email, display_name, last_sign_in_at)
SELECT
  au.id,
  COALESCE(au.email, ''),
  NULLIF(COALESCE(au.raw_user_meta_data ->> 'full_name', au.raw_user_meta_data ->> 'name', ''), ''),
  au.last_sign_in_at
FROM auth.users au
WHERE au.email IS NOT NULL
ON CONFLICT (auth_user_id)
DO UPDATE SET
  email = EXCLUDED.email,
  display_name = COALESCE(EXCLUDED.display_name, public.website_users.display_name),
  last_sign_in_at = COALESCE(EXCLUDED.last_sign_in_at, public.website_users.last_sign_in_at),
  updated_at = NOW();

-- 7) Keep website_users synced with auth.users changes
CREATE OR REPLACE FUNCTION public.sync_website_user_from_auth()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth
AS $$
BEGIN
  IF NEW.email IS NULL THEN
    RETURN NEW;
  END IF;

  INSERT INTO public.website_users (auth_user_id, email, display_name, last_sign_in_at)
  VALUES (
    NEW.id,
    NEW.email,
    NULLIF(COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.raw_user_meta_data ->> 'name', ''), ''),
    NEW.last_sign_in_at
  )
  ON CONFLICT (auth_user_id)
  DO UPDATE SET
    email = EXCLUDED.email,
    display_name = COALESCE(EXCLUDED.display_name, public.website_users.display_name),
    last_sign_in_at = COALESCE(EXCLUDED.last_sign_in_at, public.website_users.last_sign_in_at),
    updated_at = NOW();

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_website_user_from_auth ON auth.users;
CREATE TRIGGER trg_sync_website_user_from_auth
AFTER INSERT OR UPDATE OF email, raw_user_meta_data, last_sign_in_at
ON auth.users
FOR EACH ROW
EXECUTE FUNCTION public.sync_website_user_from_auth();
