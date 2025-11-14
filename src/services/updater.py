import asyncio
import json
import traceback
from pathlib import Path

from aiogram import Bot

from utils.logger import logger
from services.gsheets import load_table, sheet_changed
from storage.cache import cache
from services.notifier import NotificationService, detect_changes

CACHE_PATH = Path(__file__).resolve().parent / "../storage/cache.json"


def save_cache(data) -> None:
    """
    Сохраняет текущий кэш в файл.

    Формат:
        [
            {"tg_id": "...", "fio": "...", "role": "...", "chats": [...]},
            ...
        ]

    Файл используется при следующем запуске, чтобы бот имел актуальные данные,
    даже если таблица недоступна.
    """
    path = CACHE_PATH.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache():
    """
    Загружает данные из файла кэша при старте бота.

    Если файл отсутствует или повреждён — кэш не загружается.
    В этом случае он будет обновлён автоматически при следующем изменении таблицы.
    """
    try:
        with CACHE_PATH.resolve().open("r", encoding="utf-8") as f:
            data = json.load(f)

    except FileNotFoundError:
        logger.info("Кэш не найден — будет создан после первой загрузки таблицы")
        return

    except json.JSONDecodeError as exc:
        logger.error(f"Некорректный JSON в файле кэша: {exc}")
        return

    if not isinstance(data, list):
        logger.error("Некорректный формат кэша: ожидался список записей пользователей")
        return

    cache.clear()
    for row in data:
        if isinstance(row, dict) and "tg_id" in row:
            cache[str(row["tg_id"])] = row


async def auto_update_loop(bot: Bot, stop_event: asyncio.Event, interval: float = 2.0) -> None:
    """
    Основной фоновый цикл синхронизации с Google Sheets.

    Цикл выполняет следующие действия:
      1. Проверяет, изменилась ли таблица (sheet_changed()).
      2. При обнаружении изменений:
         - Загружает новую версию таблицы.
         - Обновляет локальный кэш.
         - Сохраняет кэш на диск.
         - Определяет изменения прав / ролей / чатов (detect_changes).
         - Отправляет соответствующие уведомления пользователям.
      3. Повторяет процесс каждые interval секунд.

    Цикл корректно завершается при установке stop_event.
    """
    logger.info("▶ Запускаю автообновление таблицы...")
    notifier = NotificationService(bot)

    while not stop_event.is_set():
        try:
            if sheet_changed():
                logger.info("🔄 Таблица изменилась — обновляю кэш")
                old_data = cache.copy()
                new_data_raw = load_table()
                save_cache(new_data_raw)
                cache.clear()
                cache.update({str(row["tg_id"]): row for row in new_data_raw})
                events = detect_changes(old_data, cache)
                for event in events:
                    asyncio.create_task(notifier.notify(event))

            await asyncio.wait_for(stop_event.wait(), timeout=interval)

        except asyncio.TimeoutError:
            continue

        except asyncio.CancelledError:
            logger.info("⏹ Остановка автообновления")
            break

        except Exception:
            logger.error("Ошибка в auto_update_loop:\n%s", traceback.format_exc())
            await asyncio.sleep(1)

    logger.info("✔ auto_update_loop завершён")
