# BACKEND-PLAN — Mia-Amore Telegram Mini App
> Составлен: 2026-04-11  
> Обновлён: 2026-04-11 (критика v1 устранена)  
> Статус: готов к разработке

---

## 0. ИСХОДНЫЕ ДАННЫЕ

**Что есть сейчас:**
- Фронтенд: чистый HTML/CSS/JS на Vercel
- Товары: хардкод в `tg-app/js/data.js`
- Заказы: имитация (`setTimeout 1s`), никуда не сохраняются
- Оплата: поле в форме, за которым ничего нет
- Bot token: есть в `.env`, бота нет

**Что должно быть:**
- Товары и категории редактируются без кода
- Фото загружаются через бота (телефон) и через веб-панель (браузер)
- Каждый заказ сохраняется и гарантированно приходит в Telegram
- Покупатели идентифицируются по Telegram ID
- Рассылка по всем покупателям (с throttle, без потерь)
- Оплата подключается позже — архитектура это учитывает

---

## 1. СТЕК

| Компонент        | Тестирование (сейчас)          | Продакшн (152-ФЗ, РФ)             |
|------------------|--------------------------------|------------------------------------|
| Backend          | Railway (free tier)            | VPS Timeweb / Beget Cloud          |
| База данных      | Supabase PostgreSQL (free)     | PostgreSQL на том же VPS           |
| Хранилище фото   | Cloudinary (free 25 GB)        | Яндекс Object Storage / VK Cloud  |
| Frontend         | Vercel (остаётся)              | Vercel (остаётся)                  |
| Bot              | python-telegram-bot (webhook)  | тот же бот, другой хост            |
| Тестовый бот     | @mia_amore_test_bot (отдельный)| —                                  |
| Фоновые задачи   | asyncio background tasks       | те же + APScheduler                |

**Язык:** Python 3.11+ / FastAPI  
*Причина: уже есть `.venv` с Pillow, Python — стандарт для Telegram-ботов*

**152-ФЗ:** личные данные (Telegram ID, имя, телефон, адрес) при переносе
на VPS обязаны лежать на серверах в РФ. Cloudinary → Яндекс при переезде.
Railway не пишет в логи персональные данные — только при VPS переезде
убедиться, что логи настроены правильно.

---

## 2. МОДЕЛИ ДАННЫХ

### 2.1 Category (категория каталога)
```
id            INTEGER PK
name          TEXT NOT NULL          -- «Халаты», «Пижамы»
slug          TEXT UNIQUE NOT NULL   -- «robe», «pijama»
sort_order    INTEGER DEFAULT 0
is_active     BOOLEAN DEFAULT true
```

### 2.2 Product (товар)
```
id              INTEGER PK
category_id     FK → Category
name            TEXT NOT NULL
material        TEXT                  -- «silk», «satin», «cotton»
material_label  TEXT                  -- «Шёлк 100%, 19 momme»
price           INTEGER NOT NULL      -- в рублях целым числом
old_price       INTEGER NULL
badge           TEXT NULL             -- «hit» | «new» | NULL
stock           INTEGER DEFAULT 0
sizes           TEXT[]                -- ['XS','S','M','L','XL']
disabled_sizes  TEXT[] DEFAULT '{}'
colors          JSONB                 -- [{"name":"Чёрный","hex":"#1C1C1E"}]
description     TEXT
care            TEXT
is_active       BOOLEAN DEFAULT true
sort_order      INTEGER DEFAULT 0
created_at      TIMESTAMPTZ DEFAULT now()
updated_at      TIMESTAMPTZ DEFAULT now()
```

### 2.3 ProductImage (фото товара)
```
id                INTEGER PK
product_id        FK → Product
storage_key       TEXT NOT NULL
  -- относительный путь: «products/1/bella-black-1.webp»
  -- НЕ полный URL — URL строится в коде через storage_provider
storage_provider  TEXT DEFAULT 'cloudinary'
  -- «cloudinary» | «yandex»
  -- при переезде меняется только это поле + конфиг, URL пересчитываются
telegram_file_id  TEXT NULL          -- если загружено через бота
sort_order        INTEGER DEFAULT 0
created_at        TIMESTAMPTZ DEFAULT now()
```
> Так решается проблема миграции: при переезде на Яндекс запускается
> скрипт, который меняет `storage_provider` и переносит файлы.
> URL в коде: `storage_service.get_url(image)` — один вызов.

### 2.4 Buyer (покупатель)
```
id              INTEGER PK
telegram_id     BIGINT UNIQUE NOT NULL
first_name      TEXT
last_name       TEXT NULL
username        TEXT NULL
phone           TEXT NULL            -- если поделился контактом
created_at      TIMESTAMPTZ DEFAULT now()
last_active_at  TIMESTAMPTZ DEFAULT now()
is_blocked      BOOLEAN DEFAULT false  -- не получает рассылки
```

### 2.5 Order (заказ)
```
id                  INTEGER PK
order_number        TEXT UNIQUE           -- «#1001», «#1002»
buyer_id            FK → Buyer NULL

status              TEXT DEFAULT 'new'
                    -- new | confirmed | shipped | delivered | cancelled

subtotal            INTEGER
discount_amount     INTEGER DEFAULT 0
delivery_cost       INTEGER DEFAULT 0
total               INTEGER

delivery_method     TEXT                  -- «cdek» | «post»
payment_method      TEXT                  -- «cod» | «online»
payment_status      TEXT DEFAULT 'pending'
                    -- pending | paid | refunded

buyer_name          TEXT NOT NULL
buyer_phone         TEXT NOT NULL
city                TEXT NOT NULL
address             TEXT NOT NULL
notes               TEXT NULL

-- Надёжность уведомлений
notification_sent   BOOLEAN DEFAULT false
  -- флаг: уведомление Денису отправлено
  -- cron проверяет false → retry каждые 5 минут

created_at          TIMESTAMPTZ DEFAULT now()
updated_at          TIMESTAMPTZ DEFAULT now()
```

### 2.6 OrderItem (позиции заказа — отдельная таблица)
```
id              INTEGER PK
order_id        FK → Order
product_id      INTEGER NULL
  -- FK → Product, но nullable: товар может быть удалён,
  -- заказ должен остаться корректным

-- snapshot данных на момент заказа (не меняется никогда)
product_name    TEXT NOT NULL         -- «Халат «Bella»»
size            TEXT NOT NULL         -- «M»
color           TEXT NOT NULL         -- «Чёрный»
qty             INTEGER NOT NULL
unit_price      INTEGER NOT NULL      -- цена на момент заказа
```
> Так решается проблема аналитики: можно запросить продажи по товару,
> по размеру, по цвету — обычным SQL без парсинга JSON.
> Пример: `SELECT product_name, SUM(qty) FROM order_item GROUP BY product_name`

### 2.7 Broadcast (рассылка)
```
id                INTEGER PK
text              TEXT NOT NULL
storage_key       TEXT NULL           -- фото рассылки (тот же storage_provider)
status            TEXT DEFAULT 'draft'
                  -- draft | sending | sent | failed
total_recipients  INTEGER DEFAULT 0   -- сколько будет отправлено
sent_count        INTEGER DEFAULT 0   -- сколько уже отправлено
failed_count      INTEGER DEFAULT 0   -- сколько не дошло (бот заблокирован)
started_at        TIMESTAMPTZ NULL
finished_at       TIMESTAMPTZ NULL
created_at        TIMESTAMPTZ DEFAULT now()
```

### 2.8 Settings (настройки магазина)
```
key     TEXT PK    -- «shop_name», «discount_active», «discount_rate»
value   TEXT
```

---

## 3. API ENDPOINTS

### Публичные (вызывает фронтенд Mini App)

```
GET  /api/categories              — список активных категорий
GET  /api/products                — список товаров (?category=robe)
GET  /api/products/{id}           — один товар с фото

POST /api/orders                  — создать заказ
     Body: { buyer_telegram_id, items[], delivery, payment, address... }
     → сохраняет Order + OrderItem[]
     → запускает фоновую задачу уведомления Дениса
     → уведомляет покупателя

POST /api/buyers/identify         — зарегистрировать/обновить покупателя
     Body: { telegram_id, first_name, last_name, username }
     → upsert Buyer, обновить last_active_at
```

**Аутентификация публичных запросов:**  
Заголовок `X-Telegram-Init-Data` с HMAC-SHA256 подписью (стандарт Telegram).  
initData проверяется не старше 24 часов (поле `auth_date`).  
В браузере (без Telegram) — принимается запрос без подписи только если
`ENVIRONMENT=development` в `.env`. В продакшне без подписи — 401.

---

### Админские (только Денис)

**Аутентификация:** Bearer-токен, заголовок `Authorization: Bearer <token>`.  
Токен генерируется командой `python -c "import secrets; print(secrets.token_hex(32))"`,
хранится в `.env`. Нет ролей, нет регистрации — один владелец.

```
# Категории
GET    /admin/categories
POST   /admin/categories
PUT    /admin/categories/{id}
DELETE /admin/categories/{id}     — только если нет товаров

# Товары
GET    /admin/products
POST   /admin/products
PUT    /admin/products/{id}
DELETE /admin/products/{id}       — мягкое удаление (is_active=false)

# Фото товара
POST   /admin/products/{id}/images          — загрузить фото (multipart)
PUT    /admin/products/{id}/images/reorder  — порядок
DELETE /admin/images/{image_id}

# Заказы
GET    /admin/orders              — список, фильтры: status, date, search
GET    /admin/orders/{id}         — детали + все OrderItem
PUT    /admin/orders/{id}/status  — сменить статус → уведомить покупателя

# Покупатели
GET    /admin/buyers
GET    /admin/buyers/{id}         — профиль + история заказов

# Рассылка
POST   /admin/broadcast           — создать, запустить фоновую отправку
GET    /admin/broadcast/{id}      — прогресс (sent_count / total_recipients)

# Аналитика (базовая)
GET    /admin/stats               — выручка за период, топ товаров, кол-во заказов
```

---

### Telegram Bot Webhook

```
POST /webhook                     — все апдейты от Telegram
```

---

## 4. ЛОГИКА TELEGRAM-БОТА

### Режим администратора (Денис)
Бот проверяет `message.from.id == ADMIN_TELEGRAM_ID` из `.env`.

**Управление товарами:**
```
/start        — главное меню с inline-кнопками
/add          — мастер добавления товара (шаги)
/products     — список с кнопками редактирования
/stock 3 5    — остаток товара #3 → 5 штук
/price 3 7990 — цена товара #3
```

**Загрузка фото (ключевая фича):**
```
Денис → отправляет фото боту
Бот   → «К какому товару привязать?» [кнопки товаров]
Денис → выбирает товар
Бот   → загружает в Cloudinary через services/storage.py
      → сохраняет storage_key в ProductImage
      → «Фото добавлено к «Халат Bella»»
```

**Управление заказами:**
```
Новый заказ — бот присылает Денису (фоновая задача, с retry):
  ┌────────────────────────────────┐
  │ 🛍 Новый заказ #1042           │
  │ Покупатель: Анна (@anna_shop)  │
  │                                │
  │ • Халат «Bella» M, Чёрный ×1  │
  │ • Пижама «Sofia» S, Роза ×2   │
  │                                │
  │ Итого: 18 970 ₽                │
  │ Доставка: СДЭК                 │
  │ Адрес: Москва, ул. Ленина 1   │
  │ Тел: +7 999 123-45-67         │
  └────────────────────────────────┘
  [✅ Подтвердить] [❌ Отменить] [📦 Отправлен]

/orders       — список новых заказов
/order 1042   — детали заказа
```

**Рассылка через бота:**
```
/broadcast    → бот просит текст
Денис вводит текст (опционально прикладывает фото)
Бот показывает превью: «Отправить 342 покупателям?»
[Да] → запускается background task (не блокирует бота)
Бот сразу отвечает: «Рассылка запущена. Прогресс: /broadcast_status»
```

### Уведомления покупателю
```
После заказа:
  «✅ Заказ #1042 принят! Скоро свяжемся с вами.»

После подтверждения:
  «📦 Заказ #1042 подтверждён и готовится к отправке.»

После отправки:
  «🚚 Заказ #1042 в пути. Трек: XXXXX (СДЭК)»
```

---

## 5. НАДЁЖНОСТЬ УВЕДОМЛЕНИЙ (критично)

Уведомления не могут быть синхронными — Telegram бывает недоступен.

### Схема для уведомления Дениса о заказе:
```
POST /api/orders
  ↓
1. Сохранить Order + OrderItem в БД (notification_sent = false)
2. Ответить покупателю 200 OK немедленно
3. Запустить background task: отправить уведомление Денису
   ├── Успех → Order.notification_sent = true
   └── Ошибка → логировать, не падать
4. APScheduler каждые 5 минут:
   SELECT * FROM orders WHERE notification_sent = false
   AND created_at > now() - interval '24 hours'
   → retry отправки
```

### Схема для рассылки (throttle обязателен):
```python
async def send_broadcast(broadcast_id: int):
    buyers = await get_active_buyers()  # is_blocked = false
    broadcast = await get_broadcast(broadcast_id)
    await update_broadcast(broadcast_id, status='sending',
                           total_recipients=len(buyers))
    for buyer in buyers:
        try:
            await bot.send_message(buyer.telegram_id, broadcast.text)
            await update_broadcast_progress(broadcast_id, sent=+1)
            await asyncio.sleep(0.05)        # 20 сообщений/сек — лимит Telegram 30
        except Forbidden:
            await mark_buyer_blocked(buyer.id)   # больше не слать
            await update_broadcast_progress(broadcast_id, failed=+1)
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after)   # Telegram просит подождать
        except Exception:
            await update_broadcast_progress(broadcast_id, failed=+1)
    await update_broadcast(broadcast_id, status='sent')
```

---

## 6. ХРАНИЛИЩЕ ФОТО (без привязки к провайдеру)

```python
# services/storage.py

class StorageService:
    def get_url(self, image: ProductImage) -> str:
        if image.storage_provider == 'cloudinary':
            return f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{image.storage_key}"
        elif image.storage_provider == 'yandex':
            return f"https://storage.yandexcloud.net/{BUCKET}/{image.storage_key}"

    async def upload(self, file: bytes, filename: str) -> str:
        """Загружает файл, возвращает storage_key"""
        key = f"products/{uuid4()}/{filename}"
        # Cloudinary или Яндекс — в зависимости от STORAGE_PROVIDER в .env
        ...
        return key
```

**Скрипт миграции Cloudinary → Яндекс (запускается один раз при переезде):**
```python
# scripts/migrate_storage.py
images = await db.execute("SELECT * FROM product_image WHERE storage_provider='cloudinary'")
for img in images:
    data = requests.get(cloudinary_url(img.storage_key)).content
    yandex_client.upload(img.storage_key, data)
    await db.execute("UPDATE product_image SET storage_provider='yandex' WHERE id=?", img.id)
```

---

## 7. КАК ФРОНТЕНД ПОДКЛЮЧАЕТСЯ К БЭКЕНДУ

```js
// tg-app/js/api.js — новый файл, заменяет data.js

const API_BASE = 'https://mia-amore-api.railway.app';

function getHeaders() {
  const initData = window.Telegram?.WebApp?.initData || '';
  return {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': initData
  };
}

async function fetchProducts(category = null) {
  const url = category
    ? `${API_BASE}/api/products?category=${category}`
    : `${API_BASE}/api/products`;
  const res = await fetch(url, { headers: getHeaders() });
  if (!res.ok) throw new Error('Ошибка загрузки каталога');
  return res.json();
}

async function createOrder(orderData) {
  const res = await fetch(`${API_BASE}/api/orders`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(orderData)
  });
  if (!res.ok) throw new Error('Ошибка оформления заказа');
  return res.json();
}
```

`catalog.js`, `product.js`, `checkout.js` получают данные через `api.js`.  
`data.js` удаляется после переноса всех 10 товаров в БД.

---

## 8. ВЕБ-ПАНЕЛЬ АДМИНИСТРАТОРА

Отдельная страница `/admin`, доступна только с Bearer-токеном.
На первом этапе — простые HTML-формы без фреймворка (быстро + надёжно).

**Разделы:**
- **Каталог**: список товаров, кнопка «+ Добавить»
- **Редактор товара**: форма + drag&drop загрузка фото
- **Категории**: список, порядок, переименование
- **Заказы**: таблица по статусам, смена статуса одной кнопкой
- **Покупатели**: список, поиск, история заказов
- **Рассылка**: форма текст + фото, превью, кнопка «Отправить»
- **Аналитика**: выручка за период, топ-5 товаров

---

## 9. ТЕСТЫ И СТЕЙДЖИНГ

### Два окружения обязательны с первого дня:

| | Staging | Production |
|---|---|---|
| Бот | @mia_amore_test_bot | @mia_amore_bot |
| БД | Supabase (отдельная база) | Supabase / VPS |
| Railway | staging service | production service |
| Vercel | Preview URL | mia-amore.vercel.app |

**Минимальный набор тестов (pytest):**
```
tests/
├── test_products.py      # GET /api/products — список, фильтрация, пустой каталог
├── test_orders.py        # POST /api/orders — валидация, сохранение OrderItem,
│                         #   notification_sent=false при старте
├── test_auth.py          # initData валидация — валидный, истёкший, подделка
├── test_broadcast.py     # throttle, Forbidden → mark_blocked, RetryAfter retry
└── conftest.py           # тестовая БД, моки Telegram API
```

**GitHub Actions (`.github/workflows/test.yml`):**
```yaml
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
```
Деплой на Railway происходит только после зелёных тестов.

---

## 10. ОПЛАТА (отложено, архитектура готова)

- `Order.payment_method` = `cod` | `online`
- `Order.payment_status` = `pending` | `paid` | `refunded`
- Endpoint `POST /api/orders/payment-callback` зарезервирован

**Когда появится ИП:**
```
Вариант A (рекомендуется): Telegram Payments
  → @BotFather → Payments → выбрать ЮKassa
  → Telegram показывает платёжную форму внутри чата
  → callback приходит в webhook: successful_payment
  → Order.payment_status = 'paid'

Вариант B: ЮKassa напрямую
  → Виджет на экране оформления
  → Webhook ЮKassa → POST /api/orders/payment-callback
  → Обновить payment_status, уведомить обоих
```

---

## 11. СТРУКТУРА ФАЙЛОВ БЭКЕНДА

```
backend/
├── main.py                    # FastAPI app, CORS, startup
├── config.py                  # Settings из .env (pydantic BaseSettings)
├── database.py                # SQLAlchemy async engine + session
├── models/
│   ├── category.py
│   ├── product.py             # Product + ProductImage
│   ├── order.py               # Order + OrderItem
│   ├── buyer.py
│   └── broadcast.py
├── routers/
│   ├── public/
│   │   ├── products.py
│   │   ├── orders.py
│   │   └── buyers.py
│   ├── admin/
│   │   ├── products.py
│   │   ├── categories.py
│   │   ├── orders.py
│   │   ├── buyers.py
│   │   └── broadcast.py
│   └── webhook.py
├── services/
│   ├── telegram_bot.py        # Хендлеры бота
│   ├── storage.py             # Cloudinary / Яндекс (единый интерфейс)
│   ├── notifications.py       # Уведомления + retry логика
│   ├── broadcast.py           # Фоновая рассылка с throttle
│   └── auth.py                # initData HMAC + Bearer-токен
├── tasks/
│   └── scheduler.py           # APScheduler: retry notification_sent=false
├── scripts/
│   └── migrate_storage.py     # Cloudinary → Яндекс при переезде
├── admin_panel/
│   ├── index.html
│   ├── products.html
│   └── orders.html
├── tests/
│   ├── conftest.py
│   ├── test_products.py
│   ├── test_orders.py
│   ├── test_auth.py
│   └── test_broadcast.py
├── migrations/                # Alembic
├── .env.example
├── requirements.txt
└── .github/workflows/test.yml
```

**.env переменные:**
```
ENVIRONMENT=development            # development | production
BOT_TOKEN=                         # Telegram Bot token (prod)
BOT_TOKEN_TEST=                    # Telegram Bot token (staging)
ADMIN_TELEGRAM_ID=                 # Telegram ID Дениса
ADMIN_API_TOKEN=                   # Bearer-токен для /admin
DATABASE_URL=                      # PostgreSQL
CLOUDINARY_URL=                    # Cloudinary credentials
STORAGE_PROVIDER=cloudinary        # cloudinary | yandex
YANDEX_BUCKET=                     # при переезде
YANDEX_KEY_ID=
YANDEX_SECRET=
FRONTEND_URL=                      # https://tg-app.vercel.app (CORS)
```

---

## 12. ПОРЯДОК РАЗРАБОТКИ

### Этап 1 — Ядро и БД ✅ ВЫПОЛНЕН (15.04.2026)
- [x] FastAPI проект, подключение Supabase
- [x] Модели: Category, Product, ProductImage, Buyer, Order, OrderItem, Broadcast
- [x] `GET /api/categories`, `GET /api/products`, `GET /api/products/{id}`
- [x] БД заполнена 10 реальными товарами с фото на Cloudinary
- [x] Бэкенд запущен локально (venv_312, Python 3.12)

### Этап 2 — Фронтенд читает из API ✅ ВЫПОЛНЕН (15.04.2026)
- [x] `api.js` — все функции: fetchProducts, fetchProduct, createOrder, identifyBuyer
- [x] Каталог и карточка товара — данные из БД
- [x] `data.js` удалён из подключения, fallback PRODUCTS убран
- [x] Деплой бэкенда на Railway: https://mia-amore-production.up.railway.app
- [x] Telegram webhook зарегистрирован
- [x] Smoke-тест в Telegram: открыть @sikretsweet_home_bot/app — каталог грузится ✅ (15.04.2026)

### Этап 3 — Заказы ✅ ВЫПОЛНЕН (15.04.2026)
- [x] `POST /api/orders` → Order + OrderItem[] сохраняются в БД
- [x] `POST /api/buyers/identify` — работает
- [x] Background task уведомления Дениса — уведомление пришло ✅
- [x] APScheduler: retry каждые 5 минут — настроен
- [x] Полный флоу протестирован: заказ → уведомление в бот ✅

### Этап 4 — Бот для Дениса ✅ ВЫПОЛНЕН (15.04.2026)
- [x] Просмотр заказов: `/orders`, `/order 1042`
- [x] Смена статуса inline-кнопками → уведомление покупателю ✅
- [x] `/broadcast` — рассылка с подтверждением
- [ ] Загрузка фото товара через бота → Cloudinary → ProductImage (отложено)

### Этап 5 — Веб-панель ✅ ВЫПОЛНЕН (15.04.2026)
- [x] Дашборд: выручка за периоды, топ товаров, последние заказы
- [x] Товары: CRUD + загрузка фото drag&drop + таблица размеров
- [x] Заказы: фильтры по статусу, поиск, смена статуса из панели
- [x] Покупатели: список
- [x] Рассылка: форма
- [x] Доступна по: https://mia-amore-production.up.railway.app/admin

### Этап 6 — Рассылка
- [ ] `POST /admin/broadcast` → фоновая задача с throttle
- [ ] `GET /admin/broadcast/{id}` — прогресс
- [ ] `/broadcast` в боте

### Этап 7 — Оплата через ЮKassa + Telegram Payments (ИП есть ✅)
> ИП подтверждён — этап можно делать сразу после Этапа 3

**Один раз руками:**
- [ ] Зарегистрироваться в ЮKassa, подключить ИП, пройти проверку (~1–3 дня)
- [ ] В @BotFather: `Payments → ЮKassa` → получить `PROVIDER_TOKEN`
- [ ] Добавить `PROVIDER_TOKEN` в Railway переменные

**В коде:**
- [ ] `POST /api/orders/invoice` — создать черновик заказа + отправить Invoice через бота
- [ ] `checkout.js` — при «Онлайн оплата» запрашивать invoice вместо прямого createOrder
- [ ] `webhook.py` — обработчик `successful_payment` → `payment_status = 'paid'`
- [ ] Уведомление покупателю «Оплата получена» + Денису
- [ ] Фолбэк: COD (наложенный платёж) остаётся без изменений

**Комиссии ЮKassa:**
- Карты (Visa/MC/Мир): ~2.5–3.5%
- СБП: 0.4–0.7%
- Наложенный платёж: 0%

### Этап 8 — Перенос на VPS (когда нужно, 152-ФЗ)
- [ ] PostgreSQL на VPS вместо Supabase
- [ ] `scripts/migrate_storage.py` → файлы на Яндекс Object Storage
- [ ] nginx + systemd + SSL (Let's Encrypt)
- [ ] Проверка 152-ФЗ: личные данные только в РФ

---

## 13. КЛЮЧЕВЫЕ РЕШЕНИЯ

| Вопрос | Решение | Почему |
|---|---|---|
| Язык бэкенда | Python / FastAPI | Есть .venv + Pillow, стандарт для TG-ботов |
| ORM | SQLAlchemy async + Alembic | PostgreSQL, миграции, типобезопасность |
| Позиции заказа | Отдельная таблица OrderItem | SQL-аналитика, корректность при удалении товара |
| Хранилище фото | storage_key + storage_provider | Миграция Cloudinary→Яндекс без боли |
| Уведомления | background task + retry cron | Гарантия доставки при недоступности Telegram |
| Рассылка | asyncio throttle 20 msg/s | Лимит Telegram 30/s, запас прочности |
| Аутентификация API | initData HMAC + auth_date | Стандарт Telegram, не нужна регистрация |
| Аутентификация admin | Bearer-токен из .env | Один владелец, не нужна сложная система |
| Тестирование | pytest + GitHub Actions | Деплой только после зелёных тестов |
| Стейджинг | Отдельный бот + Railway service | Тесты не на живых покупателях |
| Хостинг тест | Railway + Supabase | Бесплатно, деплой из GitHub |
| Хостинг прод | VPS в РФ | 152-ФЗ, личные данные |
| Оплата | Telegram Payments + ЮKassa | ИП есть; нативный UX внутри Telegram |
