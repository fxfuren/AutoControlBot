import asyncio
from aiogram.exceptions import TelegramNetworkError
from bot import bot, dp
from utils.logger import logger
from services.updater import auto_update_loop, load_cache
from handlers.start import router as start_router


async def run_polling():
    while True:
        try:
            logger.warning("▶ Запускаю polling...")
            await dp.start_polling(bot)
        except TelegramNetworkError as e:
            logger.error(f"⚠ Потеря соединения: {e}. Переподключаюсь через 5 секунд...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"❌ Ошибка polling: {e}. Перезапуск через 5 секунд...")
            await asyncio.sleep(5)


async def main():
    logger.info("🚀 Запуск бота")

    load_cache()

    dp.include_router(start_router)

    asyncio.create_task(auto_update_loop())

    # запускаем polling с авто-переподключением
    await run_polling()


if __name__ == "__main__":
    asyncio.run(main())
