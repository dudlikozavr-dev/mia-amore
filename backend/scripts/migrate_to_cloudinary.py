"""
Миграция фото из local storage → Cloudinary.

Запуск из папки backend/:
  python scripts/migrate_to_cloudinary.py
"""
import asyncio
import hashlib
import os
import sys
import time

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Загрузить .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

CLOUD_NAME   = os.environ["CLOUDINARY_CLOUD_NAME"]
API_KEY      = os.environ["CLOUDINARY_API_KEY"]
API_SECRET   = os.environ["CLOUDINARY_API_SECRET"]
DATABASE_URL = os.environ["DATABASE_URL"]

# Синхронный движок (скрипт разовый, asyncpg не нужен)
engine = create_engine(DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"))

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")


def upload_to_cloudinary(file_bytes: bytes, key: str) -> str:
    """Загружает файл в Cloudinary, возвращает storage_key."""
    public_id = os.path.splitext(key)[0]   # без расширения
    timestamp = int(time.time())
    params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
    signature = hashlib.sha1(
        (params_to_sign + API_SECRET).encode()
    ).hexdigest()

    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"https://api.cloudinary.com/v1_1/{CLOUD_NAME}/image/upload",
            data={
                "public_id": public_id,
                "timestamp": timestamp,
                "api_key": API_KEY,
                "signature": signature,
            },
            files={"file": ("image", file_bytes, "image/jpeg")},
        )
        resp.raise_for_status()

    return key  # storage_key остаётся тем же


def migrate():
    with Session(engine) as session:
        rows = session.execute(
            text("SELECT id, storage_key FROM product_image WHERE storage_provider = 'local'")
        ).fetchall()

        if not rows:
            print("Нет локальных фото — всё уже в Cloudinary или база пустая.")
            return

        print(f"Найдено {len(rows)} локальных фото. Начинаю загрузку...\n")

        ok = 0
        fail = 0

        for img_id, storage_key in rows:
            local_path = os.path.join(STATIC_DIR, storage_key)

            if not os.path.exists(local_path):
                print(f"  [SKIP]  id={img_id}  файл не найден: {local_path}")
                fail += 1
                continue

            try:
                with open(local_path, "rb") as f:
                    file_bytes = f.read()

                upload_to_cloudinary(file_bytes, storage_key)

                session.execute(
                    text(
                        "UPDATE product_image SET storage_provider = 'cloudinary' WHERE id = :id"
                    ),
                    {"id": img_id},
                )
                session.commit()

                print(f"  [OK]    id={img_id}  {storage_key}")
                ok += 1

            except Exception as e:
                session.rollback()
                print(f"  [FAIL]  id={img_id}  {storage_key}  — {e}")
                fail += 1

        print(f"\nГотово: {ok} загружено, {fail} ошибок.")


if __name__ == "__main__":
    migrate()
