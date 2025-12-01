from __future__ import annotations

import asyncio
import traceback

from typing import Mapping

from services.gsheets import load_table, sheet_changed
from services.notifier import NotificationService, detect_changes
from storage.cache import CacheRepository
from utils.logger import logger


class SheetSyncWorker:
    """Event-driven воркер синхронизации Google Sheets и локального кэша."""

    def __init__(
        self,
        cache: CacheRepository,
        notifier: NotificationService,
        *,
        interval: float = 2.0,
    ) -> None:
        self._cache = cache
        self._notifier = notifier
        self._interval = interval

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("▶ Запускаю воркер синхронизации таблицы")

        while not stop_event.is_set():
            try:
                if sheet_changed():
                    await self._handle_sheet_update()

                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("⏹ Воркер синхронизации отменён")
                break
            except Exception:
                logger.error("Ошибка в SheetSyncWorker:\n{}", traceback.format_exc())
                await asyncio.sleep(1)

        logger.info("✔ Воркер синхронизации остановлен")

    async def _handle_sheet_update(self) -> None:
        logger.info("🔄 Обнаружены изменения в таблице — обновляю кэш")
        old_data = self._cache.as_mapping()
        new_rows = load_table()
        self._cache.replace(new_rows)
        self._cache.save_snapshot()
        await self._publish_events(old_data)

    async def _publish_events(
        self, old_data: Mapping[str, Mapping[str, object]]
    ) -> None:
        events = detect_changes(old_data, self._cache.as_mapping())
        for event in events:
            await self._notifier.notify(event)
