import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADERS = [
    "Дата", "№ заказа", "Имя", "Телефон", "Город", "Адрес",
    "Примечание", "Товары", "Сумма", "Доставка", "Оплата", "Статус",
]

DELIVERY_LABELS = {"cdek": "СДЭК", "post": "Почта России"}
PAYMENT_LABELS = {"cod": "Наложенный платёж", "online": "Онлайн"}


def _get_credentials_path() -> Path | None:
    creds_path = Path(settings.google_credentials_path)
    if not creds_path.is_absolute():
        creds_path = Path(__file__).resolve().parent.parent.parent / creds_path
    return creds_path if creds_path.exists() else None


def _sync_append(row: list) -> None:
    creds_path = _get_credentials_path()
    if creds_path is None:
        raise FileNotFoundError("google-credentials.json not found")
    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(settings.google_sheets_spreadsheet_id)
    sheet = spreadsheet.sheet1
    if sheet.row_values(1) != HEADERS:
        sheet.insert_row(HEADERS, 1)
    sheet.append_row(row, value_input_option="USER_ENTERED")


async def append_order(order_data: dict) -> None:
    if not settings.google_sheets_spreadsheet_id:
        return
    try:
        items_str = "; ".join(
            f"{i['product_name']} ({i.get('size', '')} {i.get('color', '')}) ×{i['qty']}"
            for i in order_data.get("items", [])
        )
        now = datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M")
        row = [
            now,
            order_data.get("order_number", ""),
            order_data.get("buyer_name", ""),
            order_data.get("buyer_phone", ""),
            order_data.get("city", ""),
            order_data.get("address", ""),
            order_data.get("notes", "") or "",
            items_str,
            order_data.get("total", ""),
            DELIVERY_LABELS.get(order_data.get("delivery_method", ""), ""),
            PAYMENT_LABELS.get(order_data.get("payment_method", ""), ""),
            "Новый",
        ]
        await asyncio.to_thread(_sync_append, row)
        logger.info(f"Order {order_data.get('order_number')} added to Google Sheets")
    except Exception as e:
        logger.error(f"Google Sheets append error: {e}", exc_info=True)
