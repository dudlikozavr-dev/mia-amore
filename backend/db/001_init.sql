-- ============================================================
-- Mia-Amore — инициализация базы данных
-- Версия: 001
-- Запускать в Supabase SQL Editor один раз
-- ============================================================


-- ============================================================
-- 1. КАТЕГОРИИ КАТАЛОГА
-- Метафора: папки на рабочем столе — «Халаты», «Пижамы», «Сорочки»
-- ============================================================
CREATE TABLE IF NOT EXISTS category (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,                  -- «Халаты»
    slug        TEXT NOT NULL UNIQUE,           -- «robe» (для фильтров на фронте)
    sort_order  INTEGER NOT NULL DEFAULT 0,     -- порядок в меню
    is_active   BOOLEAN NOT NULL DEFAULT true   -- скрыть категорию без удаления
);

-- ============================================================
-- 2. ТОВАРЫ
-- Метафора: карточки товаров в магазине — каждая знает свою категорию
-- ============================================================
CREATE TABLE IF NOT EXISTS product (
    id              SERIAL PRIMARY KEY,
    category_id     INTEGER REFERENCES category(id) ON DELETE SET NULL,
    name            TEXT NOT NULL,
    material        TEXT,                           -- «silk», «satin», «cotton»
    material_label  TEXT,                           -- «Шёлк 100%, 19 momme»
    price           INTEGER NOT NULL CHECK (price > 0),  -- рубли, целое число
    old_price       INTEGER CHECK (old_price > 0),       -- NULL = нет старой цены
    badge           TEXT CHECK (badge IN ('hit', 'new')), -- NULL = без бейджа
    stock           INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    sizes           TEXT[] NOT NULL DEFAULT '{}',        -- ['XS','S','M','L','XL']
    disabled_sizes  TEXT[] NOT NULL DEFAULT '{}',        -- ['XL'] — нет в наличии
    colors          JSONB NOT NULL DEFAULT '[]',
    -- [{"name": "Чёрный", "hex": "#1C1C1E"}]
    description     TEXT,
    care            TEXT,                           -- инструкция по уходу
    is_active       BOOLEAN NOT NULL DEFAULT true,
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 3. ФОТОГРАФИИ ТОВАРОВ
-- Метафора: альбом с фото для каждой карточки товара.
--   storage_key — не URL, а "адрес полки" в хранилище.
--   Сам URL строится в Python-коде. Это позволяет безболезненно
--   переехать с Cloudinary на Яндекс без правки всей базы.
-- ============================================================
CREATE TABLE IF NOT EXISTS product_image (
    id                  SERIAL PRIMARY KEY,
    product_id          INTEGER NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    storage_key         TEXT NOT NULL,
    -- пример: «products/1/bella-black-1.webp»
    storage_provider    TEXT NOT NULL DEFAULT 'cloudinary'
                        CHECK (storage_provider IN ('cloudinary', 'yandex', 'local')),
    telegram_file_id    TEXT,           -- file_id из Telegram, если загружено через бота
    sort_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 4. ПОКУПАТЕЛИ
-- Метафора: записная книжка — кто когда заходил в магазин через Telegram
-- ============================================================
CREATE TABLE IF NOT EXISTS buyer (
    id              SERIAL PRIMARY KEY,
    telegram_id     BIGINT NOT NULL UNIQUE,     -- уникальный ID пользователя в Telegram
    first_name      TEXT,
    last_name       TEXT,
    username        TEXT,                        -- @username без @
    phone           TEXT,                        -- если поделился контактом
    is_blocked      BOOLEAN NOT NULL DEFAULT false,  -- true = не получает рассылки
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 5. ЗАКАЗЫ
-- Метафора: квитанция — что заказано, куда везти, как оплатить.
--   buyer_id может быть NULL: теоретически заказ без Telegram-аккаунта.
--   notification_sent — флаг для retry: если бот упал при отправке,
--     планировщик найдёт false и дошлёт уведомление.
-- ============================================================
CREATE TABLE IF NOT EXISTS "order" (
    id                  SERIAL PRIMARY KEY,
    order_number        TEXT NOT NULL UNIQUE,
    -- генерируется в Python: '#' + str(1000 + id)
    buyer_id            INTEGER REFERENCES buyer(id) ON DELETE SET NULL,

    status              TEXT NOT NULL DEFAULT 'new'
                        CHECK (status IN ('new','confirmed','shipped','delivered','cancelled')),

    subtotal            INTEGER NOT NULL CHECK (subtotal >= 0),
    discount_amount     INTEGER NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    delivery_cost       INTEGER NOT NULL DEFAULT 0 CHECK (delivery_cost >= 0),
    total               INTEGER NOT NULL CHECK (total >= 0),

    delivery_method     TEXT NOT NULL CHECK (delivery_method IN ('cdek', 'post')),
    payment_method      TEXT NOT NULL CHECK (payment_method IN ('cod', 'online')),
    payment_status      TEXT NOT NULL DEFAULT 'pending'
                        CHECK (payment_status IN ('pending', 'paid', 'refunded')),

    -- данные доставки — snapshot на момент заказа
    buyer_name          TEXT NOT NULL,
    buyer_phone         TEXT NOT NULL,
    city                TEXT NOT NULL,
    address             TEXT NOT NULL,
    notes               TEXT,

    -- надёжность уведомлений
    notification_sent   BOOLEAN NOT NULL DEFAULT false,
    -- false = уведомление ещё не дошло до Дениса → retry

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 6. ПОЗИЦИИ ЗАКАЗА (OrderItem)
-- Метафора: строки в чеке — каждая строка знает, что купили,
--   в каком размере, по какой цене *на тот момент*.
--   product_id может стать NULL если товар удалён из каталога —
--   но сам заказ при этом не ломается, имя товара сохранено.
-- ============================================================
CREATE TABLE IF NOT EXISTS order_item (
    id              SERIAL PRIMARY KEY,
    order_id        INTEGER NOT NULL REFERENCES "order"(id) ON DELETE CASCADE,
    product_id      INTEGER REFERENCES product(id) ON DELETE SET NULL,
    -- snapshot данных на момент заказа (никогда не меняется)
    product_name    TEXT NOT NULL,
    size            TEXT NOT NULL,
    color           TEXT NOT NULL,
    qty             INTEGER NOT NULL CHECK (qty > 0),
    unit_price      INTEGER NOT NULL CHECK (unit_price > 0)
    -- итог по строке = qty * unit_price (считается в Python, не хранится)
);

-- ============================================================
-- 7. РАССЫЛКИ
-- Метафора: почтовая кампания — текст + фото + прогресс отправки
-- ============================================================
CREATE TABLE IF NOT EXISTS broadcast (
    id                  SERIAL PRIMARY KEY,
    text                TEXT NOT NULL,
    storage_key         TEXT,               -- фото рассылки (опционально)
    storage_provider    TEXT DEFAULT 'cloudinary'
                        CHECK (storage_provider IN ('cloudinary', 'yandex', 'local')),
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','sending','sent','failed')),
    total_recipients    INTEGER NOT NULL DEFAULT 0,
    sent_count          INTEGER NOT NULL DEFAULT 0,
    failed_count        INTEGER NOT NULL DEFAULT 0,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- 8. НАСТРОЙКИ МАГАЗИНА
-- Метафора: папка с настройками — пары ключ/значение
-- ============================================================
CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- Начальные настройки
INSERT INTO settings (key, value) VALUES
    ('shop_name',       'Mia-Amore'),
    ('discount_active', 'false'),
    ('discount_rate',   '0.10')
ON CONFLICT (key) DO NOTHING;


-- ============================================================
-- 9. ИНДЕКСЫ — ускорение частых запросов
-- Метафора: оглавление книги — не читать всё подряд, а сразу открыть нужную страницу
-- ============================================================

-- Каталог: фильтрация активных товаров по категории
CREATE INDEX IF NOT EXISTS idx_product_category
    ON product(category_id) WHERE is_active = true;

-- Каталог: сортировка
CREATE INDEX IF NOT EXISTS idx_product_sort
    ON product(sort_order, id) WHERE is_active = true;

-- Фото: быстрый поиск фото конкретного товара
CREATE INDEX IF NOT EXISTS idx_product_image_product
    ON product_image(product_id, sort_order);

-- Заказы: фильтрация по статусу (для admin-панели)
CREATE INDEX IF NOT EXISTS idx_order_status
    ON "order"(status, created_at DESC);

-- Заказы: retry уведомлений (cron ищет notification_sent = false)
CREATE INDEX IF NOT EXISTS idx_order_notification
    ON "order"(notification_sent, created_at DESC) WHERE notification_sent = false;

-- Заказы: история заказов конкретного покупателя
CREATE INDEX IF NOT EXISTS idx_order_buyer
    ON "order"(buyer_id, created_at DESC);

-- Позиции заказа: все строки конкретного заказа
CREATE INDEX IF NOT EXISTS idx_order_item_order
    ON order_item(order_id);

-- Покупатели: поиск по Telegram ID (используется при каждом заказе)
CREATE INDEX IF NOT EXISTS idx_buyer_telegram_id
    ON buyer(telegram_id);


-- ============================================================
-- 10. ТРИГГЕР — автообновление updated_at
-- Метафора: штамп "изменено:" на документе — проставляется автоматически
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_product_updated_at
    BEFORE UPDATE ON product
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_order_updated_at
    BEFORE UPDATE ON "order"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ============================================================
-- 11. ROW LEVEL SECURITY (RLS)
-- Метафора: охрана на входе. Supabase по умолчанию открыт —
--   RLS закрывает прямой доступ извне.
--   Наш Python-бэкенд использует service_role ключ,
--   который обходит RLS — так и задумано.
--   RLS защищает от случайного прямого доступа к Supabase.
-- ============================================================
ALTER TABLE category        ENABLE ROW LEVEL SECURITY;
ALTER TABLE product         ENABLE ROW LEVEL SECURITY;
ALTER TABLE product_image   ENABLE ROW LEVEL SECURITY;
ALTER TABLE buyer           ENABLE ROW LEVEL SECURITY;
ALTER TABLE "order"         ENABLE ROW LEVEL SECURITY;
ALTER TABLE order_item      ENABLE ROW LEVEL SECURITY;
ALTER TABLE broadcast       ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings        ENABLE ROW LEVEL SECURITY;

-- Публичное чтение каталога (категории и активные товары видны всем)
-- Это нужно если когда-либо фронт будет обращаться к Supabase напрямую.
-- Сейчас фронт идёт через наш FastAPI — но пусть будет на всякий случай.
CREATE POLICY "public_read_categories"
    ON category FOR SELECT
    USING (is_active = true);

CREATE POLICY "public_read_products"
    ON product FOR SELECT
    USING (is_active = true);

CREATE POLICY "public_read_product_images"
    ON product_image FOR SELECT
    USING (true);

-- Всё остальное — только через service_role (наш бэкенд)
-- anon и authenticated пользователи не имеют доступа к заказам, покупателям и т.д.
-- Политики для этих таблиц не создаём — по умолчанию запрещено всем кроме service_role.


-- ============================================================
-- 12. НАЧАЛЬНЫЕ ДАННЫЕ — 10 товаров из data.js
-- ============================================================

-- Категории
INSERT INTO category (name, slug, sort_order) VALUES
    ('Халаты',    'robe',      1),
    ('Пижамы',    'pijama',    2),
    ('Сорочки',   'nightgown', 3),
    ('Комплекты', 'set',       4)
ON CONFLICT (slug) DO NOTHING;

-- Товары (price в рублях)
INSERT INTO product
    (category_id, name, material, material_label, price, old_price, badge,
     stock, sizes, disabled_sizes, colors, description, care, sort_order)
VALUES
(
    (SELECT id FROM category WHERE slug='robe'),
    'Халат «Bella»', 'silk', 'Шёлк натуральный',
    8990, 10990, 'hit', 6,
    ARRAY['XS','S','M','L','XL'], ARRAY[]::TEXT[],
    '[{"name":"Чёрный","hex":"#1C1C1E"},{"name":"Бордо","hex":"#6B2D3E"},{"name":"Шампань","hex":"#E8DCC8"}]',
    'Длинный халат-кимоно из натурального шёлка с поясом. Широкие рукава, глубокий запах.',
    'Ручная стирка при 30°. Не отжимать. Гладить с изнанки.',
    1
),
(
    (SELECT id FROM category WHERE slug='robe'),
    'Халат «Rosalia»', 'satin', 'Шёлковый сатин',
    5990, NULL, NULL, 12,
    ARRAY['XS','S','M','L','XL'], ARRAY['XL'],
    '[{"name":"Пудровый","hex":"#E8C8C0"},{"name":"Жемчужный","hex":"#F0EDE8"}]',
    'Короткий халат из шёлкового сатина с кружевной отделкой по рукавам и подолу.',
    'Ручная стирка при 30°. Не использовать отбеливатель.',
    2
),
(
    (SELECT id FROM category WHERE slug='pijama'),
    'Пижама «Olivia»', 'silk', 'Шёлк 100%, 19 momme',
    7490, 8990, 'new', 8,
    ARRAY['S','M','L','XL'], ARRAY[]::TEXT[],
    '[{"name":"Графит","hex":"#4A4A4E"},{"name":"Слоновая кость","hex":"#F5F0E8"}]',
    'Классическая пижама: рубашка с отложным воротником + брюки на мягкой резинке.',
    'Ручная стирка при 30°. Гладить с изнанки.',
    3
),
(
    (SELECT id FROM category WHERE slug='pijama'),
    'Пижама «Sofia» с шортами', 'satin', 'Сатин шёлковый',
    4990, NULL, 'hit', 18,
    ARRAY['XS','S','M','L'], ARRAY[]::TEXT[],
    '[{"name":"Пыльная роза","hex":"#C9A0A0"},{"name":"Чёрный","hex":"#1C1C1E"},{"name":"Лавандовый","hex":"#B8A9C9"}]',
    'Топ на тонких регулируемых бретелях с кружевом по декольте + шорты.',
    'Ручная стирка в прохладной воде. Не выжимать.',
    4
),
(
    (SELECT id FROM category WHERE slug='nightgown'),
    'Сорочка «Valentina»', 'silk', 'Шёлк с кружевом',
    5490, 6990, NULL, 3,
    ARRAY['XS','S','M','L'], ARRAY['XS'],
    '[{"name":"Чёрный","hex":"#1C1C1E"},{"name":"Бордо","hex":"#6B2D3E"}]',
    'Длинная ночная сорочка из шёлка с кружевной вставкой на груди.',
    'Только ручная стирка. Не отжимать.',
    5
),
(
    (SELECT id FROM category WHERE slug='nightgown'),
    'Сорочка «Emilia» мини', 'satin', 'Сатин + французское кружево',
    3990, NULL, 'new', 15,
    ARRAY['XS','S','M','L','XL'], ARRAY[]::TEXT[],
    '[{"name":"Пудровый","hex":"#E8C8C0"},{"name":"Чёрный","hex":"#2C2C2E"},{"name":"Молочный","hex":"#F5F0E8"}]',
    'Короткая сорочка из сатина с отделкой французским кружевом.',
    'Ручная стирка при 30°. Не использовать отбеливатель.',
    6
),
(
    (SELECT id FROM category WHERE slug='set'),
    'Комплект «Dolce Vita»', 'silk', 'Шёлк + кружево шантильи',
    12990, 15990, 'hit', 4,
    ARRAY['S','M','L'], ARRAY[]::TEXT[],
    '[{"name":"Чёрный","hex":"#1C1C1E"},{"name":"Пудровый","hex":"#E8C8C0"}]',
    'Подарочный комплект: длинный шёлковый халат-кимоно + ночная сорочка. В фирменной коробке.',
    'Только ручная стирка. Халат и сорочку стирать отдельно.',
    7
),
(
    (SELECT id FROM category WHERE slug='set'),
    'Комплект «Notte»', 'satin', 'Сатин шёлковый, 5 предметов',
    9990, NULL, NULL, 7,
    ARRAY['S','M','L','XL'], ARRAY[]::TEXT[],
    '[{"name":"Бордо","hex":"#6B2D3E"},{"name":"Графит","hex":"#4A4A4E"}]',
    'Комплект из 5 предметов: халат + рубашка + брюки + топ + шорты.',
    'Ручная стирка при 30°. Каждый предмет стирать отдельно.',
    8
),
(
    (SELECT id FROM category WHERE slug='robe'),
    'Халат «Aurora» с капюшоном', 'silk', 'Шёлк стёганый',
    11490, NULL, NULL, 5,
    ARRAY['S','M','L'], ARRAY['S'],
    '[{"name":"Жемчужный","hex":"#F0EDE8"},{"name":"Графит","hex":"#4A4A4E"}]',
    'Длинный стёганый халат из шёлка с капюшоном. Лёгкий утеплитель внутри.',
    'Деликатная машинная стирка при 30°. Сушить в расправленном виде.',
    9
),
(
    (SELECT id FROM category WHERE slug='pijama'),
    'Пижама «Lucia» брючная', 'satin', 'Сатин с кантом',
    5490, 6490, NULL, 10,
    ARRAY['XS','S','M','L','XL'], ARRAY[]::TEXT[],
    '[{"name":"Изумрудный","hex":"#2D6B5E"},{"name":"Тёмно-синий","hex":"#2C3E6B"},{"name":"Бордо","hex":"#6B2D3E"}]',
    'Рубашка с длинным рукавом и контрастным кантом + брюки на мягкой резинке.',
    'Ручная стирка при 30°. Гладить с изнанки.',
    10
);


-- ============================================================
-- ПРОВЕРКА: после запуска убедись что всё создалось
-- ============================================================
-- SELECT COUNT(*) FROM category;     -- должно быть 4
-- SELECT COUNT(*) FROM product;      -- должно быть 10
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';
