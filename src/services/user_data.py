from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


class UserDataError(ValueError):
    """Raised when user data cannot be normalised."""


_CHATS_SPLIT_RE = re.compile(r"[,\s]+")


def parse_chat_ids(raw: Any) -> list[int]:
    """Parse chat identifiers from a cell value.

    Supports strings with comma/whitespace separated identifiers or an
    iterable of identifiers. Invalid values are ignored.
    """

    values: Iterable[Any]

    if raw is None:
        return []

    if isinstance(raw, str):
        values = (part.strip() for part in _CHATS_SPLIT_RE.split(raw))
    elif isinstance(raw, Iterable) and not isinstance(raw, (bytes, bytearray)):
        values = (str(item).strip() for item in raw)
    else:
        return []

    result: list[int] = []
    seen: set[int] = set()

    for value in values:
        if not value:
            continue

        try:
            chat_id = int(value)
        except (TypeError, ValueError):
            continue

        if chat_id in seen:
            continue

        seen.add(chat_id)
        result.append(chat_id)

    return result


def normalize_user_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Normalise a raw user record coming from Google Sheets."""

    if "tg_id" not in record:
        raise UserDataError("tg_id is required")

    try:
        tg_id = int(record["tg_id"])
    except (TypeError, ValueError) as exc:
        raise UserDataError("tg_id must be an integer") from exc

    username = _clean_str(record.get("username"))
    fio = _clean_str(record.get("fio"))
    role = _clean_str(record.get("role"))

    chats_raw = record.get("chats")
    chats = parse_chat_ids(chats_raw)

    return {
        "tg_id": tg_id,
        "username": username,
        "fio": fio,
        "role": role,
        "chats": chats,
    }


def _clean_str(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()