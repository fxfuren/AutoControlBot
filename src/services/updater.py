import asyncio
import json
import traceback
from utils.logger import logger
from services.gsheets import load_table, sheet_changed
from storage.cache import cache
from services.notifier import detect_changes, notify_user
from bot import bot

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


async def auto_update_loop():
    logger.info("▶ Запускаю автообновление таблицы...")

    while True:
        try:
            if sheet_changed():
                logger.info("🔄 Таблица изменилась — обновляю кэш")

                old_data = cache.copy()

                data = load_table()
                save_cache(data)

                # обновляем память
                cache.clear()
                cache.update({str(row["tg_id"]): row for row in data})

                # ищем изменения
                events = detect_changes(old_data, cache)

                # отправляем уведомления
                for event in events:
                    asyncio.create_task(notify_user(bot, event))

        except Exception:
            logger.error("Ошибка автообновления:\n" + traceback.format_exc())

        await asyncio.sleep(2)  # комфортный интервал
