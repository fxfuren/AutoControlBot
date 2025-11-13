import json
import hashlib
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from config import GOOGLE_SHEETS_URL, GOOGLE_CREDS_PATH
from utils.logger import logger
import re

SPREADSHEET_ID = re.search(r"/d/([a-zA-Z0-9-_]+)", GOOGLE_SHEETS_URL).group(1)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Создаём API клиент один раз
creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=SCOPES)
service = build("sheets", "v4", credentials=creds)

last_modified = None
last_hash = None
last_hash_time = 0      # для debounce хэша


def load_raw_values():
    """Получение данных через batchGet (в 6 раз быстрее)."""
    result = service.spreadsheets().values().batchGet(
        spreadsheetId=SPREADSHEET_ID,
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
    try:
        meta = service.spreadsheets().get(
            spreadsheetId=SPREADSHEET_ID,
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

    except Exception:
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


def load_table():
    """Формируем таблицу в структурированный формат."""
    logger.info("📄 Загружаю Google Sheet...")

    rows = load_raw_values()
    data = []

    for row in rows:
        if not row or not row[0].strip():
            continue

        data.append({
            "tg_id": int(row[0]),
            "username": row[1] if len(row) > 1 else "",
            "fio": row[2] if len(row) > 2 else "",
            "role": row[3] if len(row) > 3 else "",
            "chats": row[4] if len(row) > 4 else "",
        })

    logger.info(f"✔ Загружено {len(data)} строк")
    return data
