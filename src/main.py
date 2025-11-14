import asyncio
import aiohttp
from aiogram.exceptions import TelegramNetworkError
from aiogram.client.session.aiohttp import AiohttpSession

from bot import bot, dp
from utils.logger import logger
from services.updater import auto_update_loop, load_cache
from handlers.start import router as start_router


async def start_bot():
    """
    Отдельная функция запуска polling — безопасная и самовосстанавливающаяся.
    """
    while True:
        try:
            logger.warning("▶ Запускаю polling...")

            # свежая сессия (исключает подвисание aiohttp)
            session = AiohttpSession()
            bot.session = session

            await dp.start_polling(bot)

        except (TelegramNetworkError, aiohttp.ClientConnectorError) as e:
            logger.error(f"⚠ Потеря связи с Telegram API: {e}. Переподключение через 5 сек...")
            await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}. Перезапуск через 5 сек...")
            await asyncio.sleep(5)


async def main():
    logger.info("🚀 Запуск бота")

    load_cache()

    # роутер подключаем ОДИН раз
    dp.include_router(start_router)

    # запускаем автообновление таблицы
    asyncio.create_task(auto_update_loop())

    # запускаем polling с авто-перезапуском
    await start_bot()


if __name__ == "__main__":
    asyncio.run(main())
