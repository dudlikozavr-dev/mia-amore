-- Остатки по размерам: {"XS": 1, "S": 2, "L": 2, "XL": 1, "2XL": 1, "3XL": 1}
-- Поле stock становится производным (сумма значений), disabled_sizes тоже
-- (размеры с 0 автоматически считаются недоступными).

ALTER TABLE product
    ADD COLUMN IF NOT EXISTS size_stock JSONB NOT NULL DEFAULT '{}';
