from __future__ import annotations

import asyncio
import gc
import traceback

from typing import Mapping

from src.services.gsheets import load_table, sheet_changed
from src.services.notifier import NotificationService, detect_changes
from src.storage.cache import CacheRepository
from src.utils.logger import logger
from src.utils.memory_monitor import log_memory_usage


class SheetSyncWorker:
    """Event-driven воркер синхронизации Google Sheets и локального кэша."""

    def __init__(
        self,
        cache: CacheRepository,
        notifier: NotificationService,
        *,
        interval: float = 10.0,  # Увеличен с 2 до 10 секунд для экономии квоты Google API
        memory_log_interval: int = 50,  # Логировать память каждые N итераций
    ) -> None:
        self._cache = cache
        self._notifier = notifier
        self._interval = interval
        self._memory_log_interval = memory_log_interval
        self._iteration_count = 0

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info("▶ Запускаю воркер синхронизации таблицы")

        while not stop_event.is_set():
            try:
                self._iteration_count += 1
                
                # Периодический мониторинг памяти
                if self._iteration_count % self._memory_log_interval == 0:
                    log_memory_usage("SheetSyncWorker")
                    gc.collect()  # Принудительная сборка мусора
                
                if sheet_changed():
                    await self._handle_sheet_update()

                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("⏹ Воркер синхронизации отменён")
                break
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Quota exceeded" in error_msg:
                    logger.warning(f"⚠️ Превышена квота Google API — пауза 60 секунд")
                    await asyncio.sleep(60)
                else:
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
        
        # Принудительная сборка мусора после обработки большого объема данных
        gc.collect()

    async def _publish_events(
        self, old_data: Mapping[str, Mapping[str, object]]
    ) -> None:
        events = detect_changes(old_data, self._cache.as_mapping())
        for event in events:
            await self._notifier.notify(event)
