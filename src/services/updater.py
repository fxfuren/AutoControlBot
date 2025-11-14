import asyncio
import json
import traceback

from aiogram import Bot

from utils.logger import logger
from services.gsheets import load_table, sheet_changed
from storage.cache import cache
from services.notifier import NotificationService, detect_changes

CACHE_PATH = "src/storage/cache.json"


def save_cache(data):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache():
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            cache.clear()
            cache.update({str(row["tg_id"]): row for row in data})
    except FileNotFoundError:
        pass


async def auto_update_loop(bot: Bot, stop_event: asyncio.Event, interval: float = 2.0) -> None:
    logger.info("▶ Запускаю автообновление таблицы...")
    notifier = NotificationService(bot)

    while not stop_event.is_set():
        try:
            if sheet_changed():
                logger.info("🔄 Таблица изменилась — обновляю кэш")

                old_data = cache.copy()

                data = load_table()
                save_cache(data)

                cache.clear()
                cache.update({str(row["tg_id"]): row for row in data})

                events = detect_changes(old_data, cache)

                for event in events:
                    asyncio.create_task(notifier.notify(event))

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("Ошибка автообновления:\n" + traceback.format_exc())

        await _sleep_with_stop(stop_event, interval)


async def _sleep_with_stop(stop_event: asyncio.Event, timeout: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        pass