"""
Скрипт наполнения БД товарами из data.js.
Запуск из папки backend/:
  python -m scripts.seed_products
"""
import asyncio
import ssl
import json
import sys
import os

# Чтобы импорты из app/ работали
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import asyncpg
from app.config import settings


PRODUCTS_DATA = [
    {
        "id": 1,
        "name": "Халат «Bella»",
        "category": "robe",
        "material": "silk",
        "material_label": "Шёлк натуральный",
        "price": 8990,
        "old_price": 10990,
        "badge": "hit",
        "stock": 6,
        "sizes": ["XS", "S", "M", "L", "XL"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Чёрный", "hex": "#1C1C1E"},
            {"name": "Бордо", "hex": "#6B2D3E"},
            {"name": "Шампань", "hex": "#E8DCC8"},
        ],
        "description": "Длинный халат-кимоно из натурального шёлка с поясом. Широкие рукава, глубокий запах. Роскошный блеск и невесомость — идеален для утреннего ритуала.",
        "care": "Ручная стирка при 30°. Не отжимать. Гладить с изнанки через ткань на минимальной температуре.",
    },
    {
        "id": 2,
        "name": "Халат «Rosalia»",
        "category": "robe",
        "material": "satin",
        "material_label": "Шёлковый сатин",
        "price": 5990,
        "old_price": None,
        "badge": None,
        "stock": 12,
        "sizes": ["XS", "S", "M", "L", "XL"],
        "disabled_sizes": ["XL"],
        "colors": [
            {"name": "Пудровый", "hex": "#E8C8C0"},
            {"name": "Жемчужный", "hex": "#F0EDE8"},
        ],
        "description": "Короткий халат из шёлкового сатина с кружевной отделкой по рукавам и подолу. Мягкий пояс в тон. Длина до середины бедра.",
        "care": "Ручная стирка при 30°. Не использовать отбеливатель. Гладить при низкой температуре.",
    },
    {
        "id": 3,
        "name": "Пижама «Olivia»",
        "category": "pijama",
        "material": "silk",
        "material_label": "Шёлк 100%, 19 momme",
        "price": 7490,
        "old_price": 8990,
        "badge": "new",
        "stock": 8,
        "sizes": ["S", "M", "L", "XL"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Графит", "hex": "#4A4A4E"},
            {"name": "Слоновая кость", "hex": "#F5F0E8"},
        ],
        "description": "Классическая пижама: рубашка с отложным воротником и перламутровыми пуговицами + брюки на мягкой резинке. Плотность шёлка 19 momme — не просвечивает.",
        "care": "Ручная стирка при 30°. Гладить с изнанки. Хранить на мягких вешалках.",
    },
    {
        "id": 4,
        "name": "Пижама «Sofia» с шортами",
        "category": "pijama",
        "material": "satin",
        "material_label": "Сатин шёлковый",
        "price": 4990,
        "old_price": None,
        "badge": "hit",
        "stock": 18,
        "sizes": ["XS", "S", "M", "L"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Пыльная роза", "hex": "#C9A0A0"},
            {"name": "Чёрный", "hex": "#1C1C1E"},
            {"name": "Лавандовый", "hex": "#B8A9C9"},
        ],
        "description": "Топ на тонких регулируемых бретелях с кружевом по декольте + шорты с кружевной отделкой. Лёгкая и женственная — идеальна для тёплых ночей.",
        "care": "Ручная стирка в прохладной воде. Не выжимать. Сушить в расправленном виде.",
    },
    {
        "id": 5,
        "name": "Сорочка «Valentina»",
        "category": "nightgown",
        "material": "silk",
        "material_label": "Шёлк с кружевом",
        "price": 5490,
        "old_price": 6990,
        "badge": None,
        "stock": 3,
        "sizes": ["XS", "S", "M", "L"],
        "disabled_sizes": ["XS"],
        "colors": [
            {"name": "Чёрный", "hex": "#1C1C1E"},
            {"name": "Бордо", "hex": "#6B2D3E"},
        ],
        "description": "Длинная ночная сорочка из шёлка с кружевной вставкой на груди и разрезом по бедру. V-образный вырез на тонких бретелях. Длина ниже колена.",
        "care": "Только ручная стирка. Не отжимать. Гладить через ткань при минимальной температуре.",
    },
    {
        "id": 6,
        "name": "Сорочка «Emilia» мини",
        "category": "nightgown",
        "material": "satin",
        "material_label": "Сатин + французское кружево",
        "price": 3990,
        "old_price": None,
        "badge": "new",
        "stock": 15,
        "sizes": ["XS", "S", "M", "L", "XL"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Пудровый", "hex": "#E8C8C0"},
            {"name": "Чёрный", "hex": "#2C2C2E"},
            {"name": "Молочный", "hex": "#F5F0E8"},
        ],
        "description": "Короткая сорочка из сатина с отделкой французским кружевом по лифу и подолу. Тонкие перекрёстные бретели на спине. Длина до середины бедра.",
        "care": "Ручная стирка при 30°. Не использовать отбеливатель. Сушить в расправленном виде.",
    },
    {
        "id": 7,
        "name": "Комплект «Dolce Vita»",
        "category": "set",
        "material": "silk",
        "material_label": "Шёлк + кружево шантильи",
        "price": 12990,
        "old_price": 15990,
        "badge": "hit",
        "stock": 4,
        "sizes": ["S", "M", "L"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Чёрный", "hex": "#1C1C1E"},
            {"name": "Пудровый", "hex": "#E8C8C0"},
        ],
        "description": "Подарочный комплект: длинный шёлковый халат-кимоно + ночная сорочка с кружевом шантильи. В фирменной коробке Mia-Amore с атласной лентой.",
        "care": "Только ручная стирка. Халат и сорочку стирать отдельно. Гладить через ткань.",
    },
    {
        "id": 8,
        "name": "Комплект «Notte»",
        "category": "set",
        "material": "satin",
        "material_label": "Сатин шёлковый, 5 предметов",
        "price": 9990,
        "old_price": None,
        "badge": None,
        "stock": 7,
        "sizes": ["S", "M", "L", "XL"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Бордо", "hex": "#6B2D3E"},
            {"name": "Графит", "hex": "#4A4A4E"},
        ],
        "description": "Комплект из 5 предметов: халат + рубашка + брюки + топ на бретелях + шорты. Всё из шёлкового сатина в одном цвете. В подарочной упаковке.",
        "care": "Ручная стирка при 30°. Каждый предмет стирать отдельно. Не использовать отбеливатель.",
    },
    {
        "id": 9,
        "name": "Халат «Aurora» с капюшоном",
        "category": "robe",
        "material": "silk",
        "material_label": "Шёлк стёганый",
        "price": 11490,
        "old_price": None,
        "badge": None,
        "stock": 5,
        "sizes": ["S", "M", "L"],
        "disabled_sizes": ["S"],
        "colors": [
            {"name": "Жемчужный", "hex": "#F0EDE8"},
            {"name": "Графит", "hex": "#4A4A4E"},
        ],
        "description": "Длинный стёганый халат из шёлка с капюшоном и накладными карманами. Лёгкий утеплитель внутри — тёплый, но не тяжёлый. Для прохладных вечеров.",
        "care": "Деликатная машинная стирка при 30°. Сушить в расправленном виде. Не гладить.",
    },
    {
        "id": 10,
        "name": "Пижама «Lucia» брючная",
        "category": "pijama",
        "material": "satin",
        "material_label": "Сатин с кантом",
        "price": 5490,
        "old_price": 6490,
        "badge": None,
        "stock": 10,
        "sizes": ["XS", "S", "M", "L", "XL"],
        "disabled_sizes": [],
        "colors": [
            {"name": "Изумрудный", "hex": "#2D6B5E"},
            {"name": "Тёмно-синий", "hex": "#2C3E6B"},
            {"name": "Бордо", "hex": "#6B2D3E"},
        ],
        "description": "Рубашка с длинным рукавом и контрастным кантом + брюки на мягкой резинке. Классический крой, перламутровые пуговицы. Выглядит дорого — стоит разумно.",
        "care": "Ручная стирка при 30°. Гладить с изнанки при низкой температуре.",
    },
]


async def seed():
    # asyncpg напрямую — без SQLAlchemy, без prepared statements (PgBouncer safe)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    conn = await asyncpg.connect(
        settings.database_url,
        ssl=ssl_ctx,
        statement_cache_size=0,   # отключаем prepared statements для PgBouncer
    )

    try:
        # Карта slug → id категорий
        rows = await conn.fetch("SELECT id, slug FROM category")
        categories = {r["slug"]: r["id"] for r in rows}
        print(f"Категории в БД: {categories}")

        # Существующие товары
        existing_rows = await conn.fetch("SELECT id FROM product")
        existing_ids = {r["id"] for r in existing_rows}
        if existing_ids:
            print(f"Товары уже есть в БД (id: {sorted(existing_ids)}). Пропускаем дубли.")

        inserted = 0
        skipped = 0

        for i, data in enumerate(PRODUCTS_DATA):
            if data["id"] in existing_ids:
                print(f"  ПРОПУСК  #{data['id']} {data['name']} (уже есть)")
                skipped += 1
                continue

            cat_id = categories.get(data["category"])
            if not cat_id:
                print(f"  ОШИБКА   #{data['id']}: категория '{data['category']}' не найдена в БД!")
                continue

            await conn.execute(
                """
                INSERT INTO product
                  (id, category_id, name, material, material_label,
                   price, old_price, badge, stock,
                   sizes, disabled_sizes, colors,
                   description, care, is_active, sort_order)
                VALUES
                  ($1, $2, $3, $4, $5,
                   $6, $7, $8, $9,
                   $10, $11, $12::jsonb,
                   $13, $14, $15, $16)
                """,
                data["id"],
                cat_id,
                data["name"],
                data["material"],
                data["material_label"],
                data["price"],
                data["old_price"],
                data["badge"],
                data["stock"],
                data["sizes"],
                data["disabled_sizes"],
                json.dumps(data["colors"], ensure_ascii=False),
                data["description"],
                data["care"],
                True,
                i + 1,
            )
            inserted += 1
            print(f"  ДОБАВЛЕН #{data['id']} {data['name']}")

        print(f"\nГотово: добавлено {inserted}, пропущено {skipped}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
