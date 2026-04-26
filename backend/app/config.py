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

    # Прокси для Telegram API (если провайдер блокирует api.telegram.org)
    # Пример: socks5://127.0.0.1:9050 (Tor)
    telegram_proxy_url: str = ""

    # ЮКасса (Telegram Payments) — для фискального чека по 54-ФЗ
    # tax_system_code: 1 ОСН, 2 УСН доходы, 3 УСН доходы-расходы, 6 Патент
    # vat_code: 1 Без НДС, 2 НДС 0%, 3 НДС 10%, 4 НДС 20%
    yookassa_tax_system_code: int = 3
    yookassa_vat_code: int = 1

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"


settings = Settings()
