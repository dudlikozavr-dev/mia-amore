-- Добавляет колонку image_type для различения фото галереи и таблицы размеров.
-- Без неё падает загрузка фото (INSERT в product_image → UndefinedColumn).

ALTER TABLE product_image
    ADD COLUMN IF NOT EXISTS image_type TEXT NOT NULL DEFAULT 'gallery'
        CHECK (image_type IN ('gallery', 'size_chart'));
