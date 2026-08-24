-- Smart Pricing: catalog categories + VAT
-- Additive migration. Does not delete or rewrite historical DailyEntry values.

ALTER TABLE product
    ADD COLUMN IF NOT EXISTS category VARCHAR(50),
    ADD COLUMN IF NOT EXISTS vat_rate DOUBLE PRECISION;

UPDATE product
SET category = CASE
    WHEN lower(trim(name)) IN ('אבוקדו','אבטיח','מלון','תפוח','בננה','בננות','מגש פירות גדול') THEN 'פירות'
    WHEN lower(trim(name)) IN ('דבש','מייפל','סילאן') THEN 'ממרחים וממתיקים'
    WHEN lower(trim(name)) IN ('שיבולת שועל') THEN 'דגנים'
    WHEN lower(trim(name)) IN ('שמן זית') THEN 'שמנים'
    WHEN lower(trim(name)) IN ('כוסות שבת') THEN 'חד-פעמי'
    ELSE COALESCE(category, 'כללי')
END
WHERE category IS NULL OR trim(category) = '';

-- Only the explicitly requested vegetable category is VAT-exempt.
UPDATE product
SET vat_rate = CASE
    WHEN category = 'ירקות' THEN 0
    ELSE 18
END
WHERE vat_rate IS NULL;

-- Keep the VAT rule consistent if a product was previously categorized as vegetables.
UPDATE product
SET vat_rate = 0
WHERE category = 'ירקות';

CREATE INDEX IF NOT EXISTS ix_product_category ON product(category);
