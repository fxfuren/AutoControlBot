from __future__ import annotations

import asyncio

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from utils.logger import logger


class BotLifecycleManager:
    """Controls polling lifecycle with graceful shutdown support."""

    def __init__(self, bot: Bot, dispatcher: Dispatcher, reconnect_delay: float = 5.0) -> None:
        self._bot = bot
        self._dispatcher = dispatcher
        self._reconnect_delay = reconnect_delay
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        logger.info("▶ Готов к запуску polling")

        while not self._stop_event.is_set():
            session = AiohttpSession()
            self._bot.session = session

            try:
                logger.warning("▶ Запускаю polling...")
                await self._dispatcher.start_polling(self._bot, stop_signal=self._stop_event.wait)
                break

            except asyncio.CancelledError:
                raise

            except (TelegramNetworkError, aiohttp.ClientConnectorError) as exc:
                logger.error(
                    "⚠ Потеря связи с Telegram API: %s. Переподключение через %.1f сек...",
                    exc,
                    self._reconnect_delay,
                )
                await self._wait_with_stop()

            except Exception as exc:  # pragma: no cover - runtime only
                logger.error("❌ Ошибка polling: %s. Перезапуск через %.1f сек...", exc, self._reconnect_delay)
                await self._wait_with_stop()

            finally:
                await session.close()

        logger.info("🛑 Polling остановлен")

    async def _wait_with_stop(self) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self._reconnect_delay)
        except asyncio.TimeoutError:
            pass

    def stop(self) -> None:
        self._stop_event.set()