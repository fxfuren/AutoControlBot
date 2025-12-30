from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot

from src.services.access_service import AccessService
from src.services.notifier import NotificationService
from src.services.updater import SheetSyncWorker
from src.storage.cache import CacheRepository


@dataclass
class ServiceContainer:
    cache: CacheRepository
    access: AccessService
    notifier: NotificationService
    sync_worker: SheetSyncWorker


_container: ServiceContainer | None = None


def init_services(bot: Bot) -> ServiceContainer:
    global _container
    cache_path = (Path(__file__).resolve().parent / "../storage/cache.json").resolve()
    cache = CacheRepository(cache_path)
    access = AccessService(cache)
    notifier = NotificationService(bot)
    sync_worker = SheetSyncWorker(cache, notifier)
    _container = ServiceContainer(cache=cache, access=access, notifier=notifier, sync_worker=sync_worker)
    return _container


def get_container() -> ServiceContainer:
    if _container is None:
        raise RuntimeError("Сервисы не инициализированы: вызовите init_services() в main")
    return _container