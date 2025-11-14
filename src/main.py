import asyncio
import signal
from contextlib import suppress

from bot import bot, dp
from handlers.start import router as start_router
from services.bot_runner import BotLifecycleManager
from services.updater import auto_update_loop, load_cache
from utils.logger import logger


async def main() -> None:
    logger.info("🚀 Запуск бота")

    load_cache()
    dp.include_router(start_router)

    stop_event = asyncio.Event()
    lifecycle = BotLifecycleManager(bot, dp)
    updater_task = asyncio.create_task(auto_update_loop(bot, stop_event))

    loop = asyncio.get_running_loop()

    def _shutdown() -> None:
        logger.info("🛑 Получен сигнал на остановку")
        lifecycle.stop()
        stop_event.set()

    for signame in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signame, _shutdown)

    try:
        await lifecycle.run()
    finally:
        stop_event.set()
        lifecycle.stop()
        updater_task.cancel()
        with suppress(asyncio.CancelledError):
            await updater_task

        with suppress(Exception):
            if bot.session:
                await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())