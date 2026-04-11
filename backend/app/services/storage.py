from app.config import settings
from app.models.product import ProductImage


class StorageService:
    """
    Единый интерфейс для хранилища фото.
    Провайдер меняется в .env — код не трогаем.
    """

    def get_url(self, image: ProductImage) -> str:
        """Возвращает полный URL фото по storage_key"""
        if image.storage_provider == "cloudinary":
            return (
                f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}"
                f"/image/upload/{image.storage_key}"
            )
        elif image.storage_provider == "yandex":
            return (
                f"https://storage.yandexcloud.net"
                f"/{settings.yandex_bucket}/{image.storage_key}"
            )
        elif image.storage_provider == "local":
            return f"/static/{image.storage_key}"
        return image.storage_key

    def get_url_by_key(self, key: str, provider: str = None) -> str:
        provider = provider or settings.storage_provider
        if provider == "cloudinary":
            return (
                f"https://res.cloudinary.com/{settings.cloudinary_cloud_name}"
                f"/image/upload/{key}"
            )
        elif provider == "yandex":
            return f"https://storage.yandexcloud.net/{settings.yandex_bucket}/{key}"
        return f"/static/{key}"


storage = StorageService()
