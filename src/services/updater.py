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
    path = CACHE_PATH.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache():
    """Загрузка кеша из файла при старте бота."""
    try:
        with CACHE_PATH.resolve().open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.info("Кэш не найден, будет создан заново")
        return
    except json.JSONDecodeError as exc:
        logger.error(f"Некорректный JSON в кэше: {exc}")
        return

    if not isinstance(data, list):
        logger.error("Некорректный формат кэша: ожидается список")
        return

    cache.clear()
    for row in data:
        if isinstance(row, dict) and "tg_id" in row:
            cache[str(row["tg_id"])] = row


async def auto_update_loop(bot: Bot, stop_event: asyncio.Event, interval: float = 2.0) -> None:
    """
    Фоновый цикл:
    - проверяет изменения в Google Sheets
    - если есть, обновляет кэш
    - определяет изменения прав/чатов
    - отправляет пользователям уведомления
    """
    logger.info("▶ Запускаю автообновление таблицы...")
    notifier = NotificationService(bot)

    while not stop_event.is_set():
        try:
            if sheet_changed():
                logger.info("🔄 Таблица изменилась — обновляю кэш")

                # делаем глубокую копию старых данных
                old_data = cache.copy()

                # загрузка новых данных
                new_data_raw = load_table()
                save_cache(new_data_raw)

                # обновляем глобальный cache
                cache.clear()
                cache.update({str(row["tg_id"]): row for row in new_data_raw})

                # определяем обновления
                events = detect_changes(old_data, cache)

                # уведомляем пользователей (асинхронно)
                for event in events:
                    asyncio.create_task(notifier.notify(event))

            # ждём перед следующей проверкой
            await asyncio.wait_for(stop_event.wait(), timeout=interval)

        except asyncio.TimeoutError:
            # нормальная ситуация — продолжаем цикл
            continue

        except asyncio.CancelledError:
            logger.info("⏹ Остановка автообновления")
            break

        except Exception as exc:
            logger.error("Ошибка в auto_update_loop:\n%s", traceback.format_exc())
            # чтобы цикл не умер
            await asyncio.sleep(1)

    logger.info("✔ auto_update_loop завершён")
