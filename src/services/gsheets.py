import json
import hashlib
import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import GOOGLE_CREDS_PATH, GOOGLE_SHEETS_URL, GOOGLE_SERVICE_TTL_MINUTES
from utils.logger import logger
from services.user_data import normalize_user_record, UserDataError

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

last_modified: datetime | None = None
last_hash: str | None = None
last_hash_time = 0.0      # для debounce хэша

# Cache for Google API service with TTL
_service_cache: dict[str, Any] = {
    "service": None,
    "created_at": 0.0
}


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


def _get_service():
    """
    Возвращает Google Sheets API service с управляемым временем жизни (TTL).
    Пересоздает service объект каждые GOOGLE_SERVICE_TTL_MINUTES минут
    для освобождения накопленных HTTP буферов и соединений.
    """
    global _service_cache
    
    current_time = time.time()
    ttl_seconds = GOOGLE_SERVICE_TTL_MINUTES * 60
    
    # Проверяем, нужно ли пересоздать service
    if (
        _service_cache["service"] is None
        or (current_time - _service_cache["created_at"]) > ttl_seconds
    ):
        # Закрываем старую HTTP сессию, если она существует
        old_service_existed = _service_cache["service"] is not None
        if old_service_existed:
            try:
                # Закрываем HTTP соединение
                if hasattr(_service_cache["service"], "_http"):
                    _service_cache["service"]._http.close()
                logger.info(
                    "♻️ Пересоздан Google API service (TTL: %d минут)",
                    GOOGLE_SERVICE_TTL_MINUTES
                )
            except Exception as exc:
                logger.warning(
                    "⚠️ Не удалось корректно закрыть старый service: %s", exc
                )
        
        # Создаем новый service
        creds_path = Path(_require_config(GOOGLE_CREDS_PATH, "GOOGLE_CREDS_PATH"))
        if not creds_path.exists():
            raise RuntimeError(f"Файл с учетными данными не найден: {creds_path}")
        
        creds = Credentials.from_service_account_file(str(creds_path), scopes=SCOPES)
        _service_cache["service"] = build("sheets", "v4", credentials=creds)
        _service_cache["created_at"] = current_time
        
        if old_service_existed:
            logger.info("✔️ Google API service успешно пересоздан")
    
    return _service_cache["service"]


def _raise_refresh_error(exc: RefreshError) -> None:
    logger.error(
        "Ошибка авторизации Google API: %s. Проверьте файл сервисного аккаунта по пути %s",
        exc,
        GOOGLE_CREDS_PATH,
    )
    raise RuntimeError(
        "Не удалось авторизоваться в Google API. Убедитесь, что GOOGLE_CREDS_PATH указывает на корректный JSON сервисного аккаунта."
    ) from exc


def load_raw_values(sheet_name: str) -> list[list[str]]:
    """Загружает указанный лист полностью (все колонки A:Z)."""
    service = _get_service()
    spreadsheet_id = _get_spreadsheet_id()

    try:
        result = service.spreadsheets().values().batchGet(
            spreadsheetId=spreadsheet_id,
            ranges=[f"{sheet_name}!A1:Z9999"]
        ).execute()
    except RefreshError as exc:
        _raise_refresh_error(exc)

    values = result["valueRanges"][0].get("values", [])
    
    # Явно удаляем большой объект result для освобождения памяти
    del result
    
    return values


# ===========================
#        ВАЛИДАЦИЯ
# ===========================

def validate_table(access_raw: list[list[str]], mapping_raw: list[list[str]]):
    logger.info("🔍 Проверяю таблицу...")

    if not access_raw:
        raise RuntimeError("Лист 'Доступы' пуст")

    if not mapping_raw:
        raise RuntimeError("Лист 'Чаты' пуст")

    headers = access_raw[0]

    required_cols = {"tg_id", "username", "fio"}
    missing = required_cols - set(headers)
    if missing:
        raise RuntimeError(f"В листе 'Доступы' отсутствуют обязательные колонки: {missing}")

    chat_columns = [h for h in headers if h not in required_cols]
    if not chat_columns:
        raise RuntimeError("В листе 'Доступы' нет колонок чатов")

    # ────────────────────────
    #  ВАЛИДАЦИЯ ЛИСТА "ЧАТЫ"
    # ────────────────────────

    chat_name_to_id = {}

    for row in mapping_raw[1:]:
        # Пустая строка → пропускаем
        if not row or all(not cell.strip() for cell in row):
            continue

        chat_name = row[0].strip() if len(row) >= 1 else ""
        chat_id = row[1].strip() if len(row) >= 2 else ""

        if not chat_name:
            logger.warning("⚠️ Пропускаю строку в 'Чаты': пустое название чата")
            continue

        if chat_name in chat_name_to_id:
            raise RuntimeError(f"Дублируется название чата в листе 'Чаты': {chat_name}")

        if not chat_id:
            logger.warning(f"⚠️ Чат '{chat_name}' не имеет chat_id — пропускаю")
            continue  # важно: просто пропускаем

        if not chat_id.startswith("-100"):
            logger.warning(f"⚠️ Возможно некорректный chat_id '{chat_id}' для чата '{chat_name}'")

        chat_name_to_id[chat_name] = chat_id

    if not chat_name_to_id:
        raise RuntimeError("В листе 'Чаты' нет ни одного корректного чата")

    # Проверяем соответствие заголовков чатов
    for col in chat_columns:
        if col not in chat_name_to_id:
            logger.warning(
                f"⚠️ Колонка '{col}' есть в 'Доступы', "
                f"но отсутствует в листе 'Чаты' — пользователи не получат этот чат"
            )

    # ────────────────────────
    #  ПРОВЕРКА tg_id
    # ────────────────────────

    seen = set()
    for row in access_raw[1:]:
        if not row or not row[0].strip():
            continue

        tg = row[0].strip()

        if not tg.isdigit():
            raise RuntimeError(f"Некорректный tg_id: '{tg}'")

        if tg in seen:
            raise RuntimeError(f"Дублирующийся tg_id: {tg}")

        seen.add(tg)

    logger.info("✔ Валидация успешно пройдена")


# ===========================
#      ОПРЕДЕЛЕНИЕ ИЗМЕНЕНИЙ
# ===========================

def sheet_changed():
    """
    Определение изменений:
    1) modifiedTime (мгновенно)
    2) fallback-хэш с debounce (1 раз в 10 сек)
    """
    global last_modified, last_hash, last_hash_time

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

    except RefreshError as exc:
        _raise_refresh_error(exc)
    except HttpError:
        pass

    now = time.time()

    if now - last_hash_time < 10:
        return False

    last_hash_time = now

    rows = load_raw_values("Доступы")
    new_hash = hashlib.md5(json.dumps(rows, sort_keys=True).encode()).hexdigest()

    if last_hash is None:
        last_hash = new_hash
        return True

    if new_hash != last_hash:
        last_hash = new_hash
        return True

    return False


# ===========================
#      ЗАГРУЗКА ТАБЛИЦЫ
# ===========================

def load_table() -> list[dict[str, Any]]:
    logger.info("📄 Загружаю Google Sheet...")

    access_raw = load_raw_values("Доступы")
    mapping_raw = load_raw_values("Чаты")

    # ---- ВАЛИДАЦИЯ ----
    validate_table(access_raw, mapping_raw)

    headers = access_raw[0]
    rows = access_raw[1:]

    # Собираем соответствие чатов
    chat_name_to_id = {
        row[0].strip(): row[1].strip()
        for row in mapping_raw[1:]
        if len(row) >= 2 and row[0].strip()
    }
    
    # Освобождаем память от больших промежуточных объектов
    del mapping_raw

    data = []

    for row in rows:
        if not row or not row[0].strip():
            continue

        row_dict = dict(zip(headers, row))

        tg_id = row_dict.get("tg_id", "").strip()
        if not tg_id:
            continue

        # доступные чаты
        user_chats = []
        for col_name, value in row_dict.items():
            if col_name in ("tg_id", "username", "fio"):
                continue
            if value.strip() == "+":
                chat_id = chat_name_to_id.get(col_name)
                if chat_id:
                    user_chats.append(chat_id)
                else:
                    logger.warning(
                        f"⚠️ В таблице 'Доступы' указано '+', "
                        f"но чат '{col_name}' отсутствует в листе 'Чаты' – пропускаю"
                    )



        record = {
            "tg_id": tg_id,
            "username": row_dict.get("username", ""),
            "fio": row_dict.get("fio", ""),
            "chats": user_chats,
        }

        try:
            data.append(normalize_user_record(record))
        except UserDataError as exc:
            logger.warning("Пропускаю строку tg_id=%s: %s", tg_id, exc)
    
    # Освобождаем память от больших промежуточных объектов
    del access_raw
    del rows

    logger.info(f"✔ Загружено {len(data)} строк")
    return data
