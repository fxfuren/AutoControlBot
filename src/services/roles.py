from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from storage.cache import cache


def get_user_by_tg_id(tg_id: int) -> Optional[Dict[str, Any]]:
    user = cache.get(str(tg_id))
    if user is None:
        return None

    return deepcopy(user)


def get_user_chats(tg_id: int) -> List[int]:
    user = cache.get(str(tg_id))

    if not user:
        return []

    chats = user.get("chats") or []
    return list(chats)