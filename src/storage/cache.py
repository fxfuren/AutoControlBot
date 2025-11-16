from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from utils.logger import logger


class CacheRepository:
    """Локальный кэш как мини-репозиторий данных из Google Sheets."""

    def __init__(self, snapshot_path: Path) -> None:
        self._snapshot_path = snapshot_path
        self._data: Dict[str, Dict[str, Any]] = {}

    @property
    def path(self) -> Path:
        return self._snapshot_path

    def load_from_disk(self) -> None:
        """Загружает данные из json снапшота, если он существует."""
        try:
            raw = self._snapshot_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.info("Кэш не найден — будет создан после первой синхронизации")
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Не удалось разобрать cache.json — начинаем с пустого состояния")
            return

        if not isinstance(data, list):
            logger.warning("Некорректный формат cache.json — ожидается список объектов")
            return

        self.replace(data)

    def save_snapshot(self) -> None:
        """Сохраняет текущее состояние в json."""
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = list(self._data.values())
        self._snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def replace(self, rows: Iterable[Mapping[str, Any]]) -> None:
        """Полностью заменяет содержимое кэша новыми строками."""
        new_data: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            tg_id = row.get("tg_id")
            if tg_id is None:
                continue
            new_data[str(tg_id)] = dict(row)
        self._data = new_data

    def snapshot(self) -> Dict[str, Dict[str, Any]]:
        """Возвращает копию текущего состояния для анализа изменений."""
        return deepcopy(self._data)

    def get_user(self, tg_id: int) -> Dict[str, Any] | None:
        user = self._data.get(str(tg_id))
        return deepcopy(user) if user else None

    def list_user_chats(self, tg_id: int) -> list[int]:
        user = self._data.get(str(tg_id))
        if not user:
            return []
        chats = user.get("chats") or []
        result: list[int] = []
        for chat in chats:
            try:
                result.append(int(chat))
            except (TypeError, ValueError):
                continue
        return result

    def as_mapping(self) -> Mapping[str, Mapping[str, Any]]:
        return self._data