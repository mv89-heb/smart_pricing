-- Product price consistency
-- Keep one current price per product in the price list.
-- Historical DailyEntry.unit_price values remain unchanged.

-- Normalize product names before matching historical entries.
WITH latest_prices AS (
    SELECT DISTINCT ON (LOWER(TRIM(product_name)))
        LOWER(TRIM(product_name)) AS normalized_name,
        unit_price
    FROM daily_entry
    WHERE unit_price IS NOT NULL
    ORDER BY LOWER(TRIM(product_name)), id DESC
)
UPDATE product AS p
SET price = lp.unit_price
FROM latest_prices AS lp
WHERE LOWER(TRIM(p.name)) = lp.normalized_name
  AND p.price IS DISTINCT FROM lp.unit_price;
