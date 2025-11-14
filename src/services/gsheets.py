import json
import hashlib
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import GOOGLE_CREDS_PATH, GOOGLE_SHEETS_URL
from utils.logger import logger
from services.user_data import normalize_user_record, UserDataError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

last_modified: datetime | None = None
last_hash: str | None = None
last_hash_time = 0.0      # для debounce хэша


def _require_config(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Переменная окружения {name} не настроена")
    return value


@lru_cache(maxsize=1)
def _get_spreadsheet_id() -> str:
    url = _require_config(GOOGLE_SHEETS_URL, "GOOGLE_SHEETS_URL")
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if not match:
        raise RuntimeError("Не удалось определить идентификатор таблицы из GOOGLE_SHEETS_URL")
    return match.group(1)


@lru_cache(maxsize=1)
def _get_service():
    creds_path = Path(_require_config(GOOGLE_CREDS_PATH, "GOOGLE_CREDS_PATH"))
    if not creds_path.exists():
        raise RuntimeError(f"Файл с учетными данными не найден: {creds_path}")

    creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def load_raw_values() -> list[list[str]]:
    """Получение данных через batchGet (в 6 раз быстрее)."""
    service = _get_service()
    spreadsheet_id = _get_spreadsheet_id()

    result = service.spreadsheets().values().batchGet(
        spreadsheetId=spreadsheet_id,
        ranges=["Лист1!A2:E"]
    ).execute()

    values = result.get("valueRanges", [])[0].get("values", [])
    return values


def sheet_changed():
    """
    Определение изменений:
    1) modifiedTime (мгновенно)
    2) fallback-хэш с debounce (1 раз в 10 сек)
    """
    global last_modified, last_hash, last_hash_time

    # ---------------------- Проверяем modifiedTime ----------------------
    service = _get_service()
    spreadsheet_id = _get_spreadsheet_id()

    try:
        meta = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            fields="properties.modifiedTime"
        ).execute()

        modified = meta["properties"]["modifiedTime"]
        new_time = datetime.fromisoformat(modified.replace("Z", "+00:00"))

        if last_modified is None:
            last_modified = new_time
            return True

        if new_time != last_modified:
            last_modified = new_time
            return True

        return False

    except HttpError:
        pass  # если нет modifiedTime → берём fallback

    # ---------------------- Fallback: debounce + hash ----------------------
    import time
    now = time.time()

    # Fallback check раз в 10 секунд — debounce
    if now - last_hash_time < 10:
        return False

    last_hash_time = now

    rows = load_raw_values()
    new_hash = hashlib.md5(json.dumps(rows, sort_keys=True).encode()).hexdigest()

    if last_hash is None:
        last_hash = new_hash
        return True

    if new_hash != last_hash:
        last_hash = new_hash
        return True

    return False


def load_table() -> list[dict[str, Any]]:
    """Формируем таблицу в структурированный формат."""
    logger.info("📄 Загружаю Google Sheet...")

    rows = load_raw_values()
    data = []

    for row in rows:
        if not row or not row[0].strip():
            continue

        record = {
            "tg_id": row[0],
            "username": row[1] if len(row) > 1 else "",
            "fio": row[2] if len(row) > 2 else "",
            "role": row[3] if len(row) > 3 else "",
            "chats": row[4] if len(row) > 4 else "",
        }

        try:
            data.append(normalize_user_record(record))
        except UserDataError as exc:
            logger.warning("Пропускаю строку с tg_id=%s: %s", record.get("tg_id"), exc)
            continue

    logger.info(f"✔ Загружено {len(data)} строк")
    return data