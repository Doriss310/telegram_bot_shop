-- Product position sorting migration
-- NOTE: keep this in a separate SQL file (do not append to old schema files)

ALTER TABLE public.products
  ADD COLUMN IF NOT EXISTS sort_position INTEGER;

CREATE INDEX IF NOT EXISTS idx_products_sort_position
  ON public.products (sort_position, id);

COMMENT ON COLUMN public.products.sort_position IS
  'Manual position for bot product ordering (ascending). NULL means fallback to id order.';
