from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Путь к .env всегда от папки backend/, независимо откуда запущен сервер
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Окружение
    environment: str = "development"

    # Telegram
    bot_token: str = ""
    bot_token_test: str = ""
    admin_telegram_id: int = 0
    payment_provider_token: str = ""

    # Безопасность
    admin_api_token: str = ""

    # База данных
    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Хранилище фото
    storage_provider: str = "cloudinary"
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # CORS
    frontend_url: str = "http://localhost:3000"

    # URL бэкенда (для регистрации webhook)
    # Пример: https://mia-amore-api.up.railway.app
    backend_url: str = ""

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"


settings = Settings()
