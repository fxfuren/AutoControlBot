from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from storage.cache import cache


def get_user_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает полную запись пользователя по Telegram ID (tg_id).

    Данные берутся из кэша Google Sheets:
        cache[str(tg_id)] → dict с полями (fio, role, chats и т.п.)

    Возвращается *копия* записи, чтобы вызывающий код не мог случайно
    изменить данные внутри кэша.
    """
    user = cache.get(str(tg_id))
    if user is None:
        return None

    return deepcopy(user)


def get_user_chats(tg_id: int) -> List[int]:
    """
    Возвращает список ID чатов, доступных пользователю.

    Если пользователя нет в кэше — возвращается пустой список.
    Если поле "chats" отсутствует или пустое — тоже возвращается [].

    Значение приводится к обычному списку int.
    """
    user = cache.get(str(tg_id))
    if not user:
        return []

    chats = user.get("chats") or []
    return list(chats)
