-- Product soft-delete/hide migration
-- NOTE: keep this in a separate SQL file (do not append to old schema files)

-- 1) Add visibility + soft-delete columns on products
ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_products_visibility
  ON public.products (is_deleted, is_hidden, id);

-- Defensive cleanup for older rows (if columns were added without NOT NULL/default in prior experiments)
UPDATE public.products
SET is_hidden = COALESCE(is_hidden, FALSE),
    is_deleted = COALESCE(is_deleted, FALSE)
WHERE is_hidden IS NULL OR is_deleted IS NULL;

-- 2) Rebuild stock RPCs so customer-facing product listing ignores hidden/soft-deleted products
DROP FUNCTION IF EXISTS public.get_products_with_stock();
CREATE OR REPLACE FUNCTION public.get_products_with_stock()
RETURNS TABLE (
  id bigint,
  name text,
  price bigint,
  price_usdt numeric,
  price_tiers jsonb,
  promo_buy_quantity integer,
  promo_bonus_quantity integer,
  website_name text,
  website_price bigint,
  website_price_tiers jsonb,
  website_promo_buy_quantity integer,
  website_promo_bonus_quantity integer,
  website_banner_url text,
  website_logo_url text,
  website_enabled boolean,
  description text,
  format_data text,
  stock bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    p.id,
    p.name,
    p.price,
    p.price_usdt,
    p.price_tiers,
    p.promo_buy_quantity,
    p.promo_bonus_quantity,
    p.website_name,
    p.website_price,
    p.website_price_tiers,
    p.website_promo_buy_quantity,
    p.website_promo_bonus_quantity,
    p.website_banner_url,
    p.website_logo_url,
    p.website_enabled,
    p.description,
    p.format_data,
    COALESCE(s.stock, 0) AS stock
  FROM public.products p
  LEFT JOIN (
    SELECT product_id, COUNT(*) AS stock
    FROM public.stock
    WHERE sold = FALSE
    GROUP BY product_id
  ) s ON s.product_id = p.id
  WHERE (auth.role() = 'service_role' OR public.is_admin())
    AND COALESCE(p.is_deleted, FALSE) = FALSE
    AND COALESCE(p.is_hidden, FALSE) = FALSE
  ORDER BY p.id;
$$;

DROP FUNCTION IF EXISTS public.get_product_with_stock(bigint);
CREATE OR REPLACE FUNCTION public.get_product_with_stock(p_id bigint)
RETURNS TABLE (
  id bigint,
  name text,
  price bigint,
  price_usdt numeric,
  price_tiers jsonb,
  promo_buy_quantity integer,
  promo_bonus_quantity integer,
  website_name text,
  website_price bigint,
  website_price_tiers jsonb,
  website_promo_buy_quantity integer,
  website_promo_bonus_quantity integer,
  website_banner_url text,
  website_logo_url text,
  website_enabled boolean,
  description text,
  format_data text,
  stock bigint
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT
    p.id,
    p.name,
    p.price,
    p.price_usdt,
    p.price_tiers,
    p.promo_buy_quantity,
    p.promo_bonus_quantity,
    p.website_name,
    p.website_price,
    p.website_price_tiers,
    p.website_promo_buy_quantity,
    p.website_promo_bonus_quantity,
    p.website_banner_url,
    p.website_logo_url,
    p.website_enabled,
    p.description,
    p.format_data,
    COALESCE(s.stock, 0) AS stock
  FROM public.products p
  LEFT JOIN (
    SELECT product_id, COUNT(*) AS stock
    FROM public.stock
    WHERE sold = FALSE
    GROUP BY product_id
  ) s ON s.product_id = p.id
  WHERE (auth.role() = 'service_role' OR public.is_admin())
    AND p.id = p_id
    AND COALESCE(p.is_deleted, FALSE) = FALSE
    AND COALESCE(p.is_hidden, FALSE) = FALSE
  LIMIT 1;
$$;

-- 3) Optional helper function for soft delete (keeps FK-referenced orders intact)
CREATE OR REPLACE FUNCTION public.soft_delete_product(p_product_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NOT (auth.role() = 'service_role' OR public.is_admin()) THEN
    RAISE EXCEPTION 'not authorized';
  END IF;

  UPDATE public.products
  SET
    is_hidden = TRUE,
    is_deleted = TRUE,
    deleted_at = NOW()
  WHERE id = p_product_id;
END;
$$;
