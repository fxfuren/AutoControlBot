"""Utility module with a tiny async-friendly JSON key-value storage."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict


class JsonKeyValueStore:
    """Simple JSON backed storage with in-memory caching.

    The store keeps data in memory and persists it on each mutation.
    File operations are executed in a thread pool so we do not block the
    event loop. The class is intentionally small but gives us a centralised
    place to manage tiny persistent dictionaries.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = asyncio.Lock()
        self._data: Dict[str, Any] | None = None

    async def _ensure_loaded(self) -> None:
        if self._data is not None:
            return

        async with self._lock:
            if self._data is not None:
                return

            def _load() -> Dict[str, Any]:
                if not self._path.exists():
                    return {}
                try:
                    with self._path.open("r", encoding="utf-8") as fh:
                        return json.load(fh)
                except json.JSONDecodeError:
                    # Corrupted file — start from scratch but do not crash the bot.
                    return {}

            self._data = await asyncio.to_thread(_load)

    async def get(self, key: str, default: Any | None = None) -> Any:
        await self._ensure_loaded()
        assert self._data is not None
        return self._data.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        await self._ensure_loaded()
        assert self._data is not None

        async with self._lock:
            self._data[key] = value
            await self._flush()

    async def delete(self, key: str) -> None:
        await self._ensure_loaded()
        assert self._data is not None

        async with self._lock:
            if key in self._data:
                del self._data[key]
                await self._flush()

    async def _flush(self) -> None:
        assert self._data is not None

        def _dump(data: Dict[str, Any]) -> None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)

        await asyncio.to_thread(_dump, dict(self._data))