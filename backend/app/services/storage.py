"""
StorageService — единый интерфейс для хранилища фото.

Провайдер задаётся в .env (STORAGE_PROVIDER=cloudinary|local).
При переезде на Яндекс: меняем переменную + запускаем scripts/migrate_storage.py.

get_url(image)  — строит полный URL из storage_key
upload(file, filename, product_id) — загружает файл, возвращает storage_key
"""
import logging
import os
from uuid import uuid4

from app.config import settings
from app.models.product import ProductImage

logger = logging.getLogger(__name__)


class StorageService:

    # ─── URL ─────────────────────────────────────────────────────────────────

    def get_url(self, image: ProductImage) -> str:
        """Возвращает полный URL фото по storage_key."""
        return self.get_url_by_key(image.storage_key, image.storage_provider)

    def get_url_by_key(self, key: str, provider: str = None) -> str:
        provider = provider or settings.storage_provider
        if provider == "cloudinary":
            return (
                f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}"
                f"/image/upload/{key}"
            )
        elif provider == "yandex":
            return f"https://storage.yandexcloud.net/{settings.yandex_bucket}/{key}"
        # local / fallback
        return f"/static/uploads/{key}"

    # ─── Upload ───────────────────────────────────────────────────────────────

    async def upload(self, file_bytes: bytes, filename: str, product_id: int) -> tuple[str, str]:
        """
        Загружает файл в хранилище.
        Возвращает (storage_key, storage_provider).
        """
        ext = os.path.splitext(filename)[1].lower() or ".jpg"
        key = f"products/{product_id}/{uuid4().hex}{ext}"
        provider = settings.storage_provider

        if provider == "cloudinary":
            return await self._upload_cloudinary(file_bytes, key), provider
        else:
            return await self._upload_local(file_bytes, key), "local"

    async def _upload_cloudinary(self, file_bytes: bytes, key: str) -> str:
        """Загружает в Cloudinary через REST API (без SDK — чтобы не тащить sync)."""
        import hashlib
        import hmac as _hmac
        import time
        import httpx

        timestamp = int(time.time())
        # Cloudinary public_id = key без расширения
        public_id = os.path.splitext(key)[0]

        # Подпись
        params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
        signature = hashlib.sha1(
            (params_to_sign + settings.cloudinary_api_secret).encode()
        ).hexdigest()

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/upload",
                data={
                    "public_id": public_id,
                    "timestamp": timestamp,
                    "api_key": settings.cloudinary_api_key,
                    "signature": signature,
                },
                files={"file": ("image", file_bytes, "image/jpeg")},
            )
            resp.raise_for_status()

        return key

    async def _upload_local(self, file_bytes: bytes, key: str) -> str:
        """Сохраняет файл в backend/static/uploads/ (только для локальной разработки)."""
        import aiofiles
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "uploads")
        full_path = os.path.join(base_dir, key)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        async with aiofiles.open(full_path, "wb") as f:
            await f.write(file_bytes)

        return key

    async def delete(self, image: ProductImage) -> None:
        """Удаляет файл из хранилища (best-effort, ошибки не пробрасываются)."""
        try:
            if image.storage_provider == "cloudinary":
                await self._delete_cloudinary(image.storage_key)
            elif image.storage_provider == "local":
                await self._delete_local(image.storage_key)
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {image.storage_key}: {e}")

    async def _delete_cloudinary(self, key: str) -> None:
        import hashlib
        import time
        import httpx

        public_id = os.path.splitext(key)[0]
        timestamp = int(time.time())
        params_to_sign = f"public_id={public_id}&timestamp={timestamp}"
        signature = hashlib.sha1(
            (params_to_sign + settings.cloudinary_api_secret).encode()
        ).hexdigest()

        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(
                f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/image/destroy",
                data={
                    "public_id": public_id,
                    "timestamp": timestamp,
                    "api_key": settings.cloudinary_api_key,
                    "signature": signature,
                },
            )

    async def _delete_local(self, key: str) -> None:
        import aiofiles.os as aio_os
        base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "uploads")
        full_path = os.path.join(base_dir, key)
        await aio_os.remove(full_path)


storage = StorageService()
