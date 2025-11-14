"""Notification and change detection utilities."""
from __future__ import annotations

import asyncio
import html
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Mapping, Optional

from aiogram import Bot, types

from services.chat_utils import ensure_invite_link, get_chat
from services.user_data import parse_chat_ids
from utils.logger import logger


@dataclass(slots=True)
class UserChangeEvent:
    tg_id: int
    changed_role: Optional[tuple[str, str]] = None
    new_chats: List[int] = field(default_factory=list)
    removed_chats: List[int] = field(default_factory=list)


class NotificationBuilder:
    """Builds a notification message describing access changes."""

    async def build(self, bot: Bot, event: UserChangeEvent) -> Optional[str]:
        lines: List[str] = ["<b>🔔 Обновление доступа</b>"]
        chat_cache: dict[int, Optional[types.Chat]] = {}

        async def _chat(chat_id: int) -> Optional[types.Chat]:
            if chat_id not in chat_cache:
                chat_cache[chat_id] = await get_chat(bot, chat_id)
            return chat_cache[chat_id]

        async def _title(chat_id: int) -> Optional[str]:
            chat = await _chat(chat_id)
            return chat.title if chat else None

        async def _invite(chat_id: int) -> Optional[str]:
            chat = await _chat(chat_id)
            return await ensure_invite_link(bot, chat_id, chat)

        if event.changed_role:
            old_role, new_role = (html.escape(x) for x in event.changed_role)
            lines.extend([
                "\n🎭 <b>Изменение роли</b>",
                f"• Было: <code>{old_role or '-'}</code>",
                f"• Стало: <code>{new_role or '-'}</code>",
            ])

        if event.new_chats:
            lines.append("\n📥 <b>Доступ к новым чатам</b>")
            for chat_id in event.new_chats:
                invite = await _invite(chat_id)
                if not invite:
                    logger.warning("[notifier] Нет ссылки-приглашения для чата %s", chat_id)
                    continue

                title = await _title(chat_id)
                link_text = html.escape(title or str(chat_id))
                lines.append(f"• <a href=\"{invite}\">{link_text}</a>")

        if event.removed_chats:
            lines.append("\n🚫 <b>Доступ ограничен</b>")
            for chat_id in event.removed_chats:
                title = await _title(chat_id)
                name = html.escape(title or str(chat_id))
                lines.append(f"• {name}")
                await _kick_from_chat(bot, event.tg_id, chat_id)

        return "\n".join(lines) if len(lines) > 1 else None


class NotificationService:
    """Send notifications to users about their access changes."""

    def __init__(self, bot: Bot, *, delay: float = 0.0) -> None:
        self._bot = bot
        self._delay = max(0.0, delay)
        self._builder = NotificationBuilder()

    async def notify(self, event: UserChangeEvent) -> None:
        message = await self._builder.build(self._bot, event)
        if not message:
            return

        try:
            await self._bot.send_message(
                event.tg_id,
                message,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
        except Exception as exc:  # pragma: no cover - network errors
            logger.error("[notifier] Не удалось отправить уведомление %s: %s", event.tg_id, exc)
            return

        if self._delay:
            await asyncio.sleep(self._delay)


def detect_changes(
    old_data: Mapping[str, Mapping[str, Any]],
    new_data: Mapping[str, Mapping[str, Any]],
) -> List[UserChangeEvent]:
    """Compare cached data and return events describing the difference."""

    events: List[UserChangeEvent] = []
    processed: set[str] = set()

    for key, new in new_data.items():
        tg_id = _extract_tg_id(new)
        if tg_id is None:
            continue

        processed.add(key)
        old = old_data.get(key)

        new_role = _extract_role(new)
        old_role = _extract_role(old)

        changed_role: Optional[tuple[str, str]] = None
        if new_role != old_role:
            changed_role = (old_role, new_role)

        new_chats = _chat_ids(new)
        old_chats = _chat_ids(old)

        added = sorted(new_chats - old_chats)
        removed = sorted(old_chats - new_chats)

        if changed_role or added or removed or old is None:
            events.append(
                UserChangeEvent(
                    tg_id=tg_id,
                    changed_role=changed_role,
                    new_chats=added,
                    removed_chats=removed,
                )
            )

    for key, old in old_data.items():
        if key in processed:
            continue

        tg_id = _extract_tg_id(old)
        if tg_id is None:
            continue

        removed_chats = sorted(_chat_ids(old))
        if removed_chats:
            events.append(UserChangeEvent(tg_id=tg_id, removed_chats=removed_chats))

    return events


def _extract_tg_id(record: Mapping[str, Any] | None) -> Optional[int]:
    if not record:
        return None
    try:
        return int(record.get("tg_id"))
    except (TypeError, ValueError):
        logger.warning("[notifier] Некорректный tg_id в записи: %s", record)
        return None


def _extract_role(record: Mapping[str, Any] | None) -> str:
    if not record:
        return ""
    role = record.get("role", "")
    return str(role).strip()


def _chat_ids(record: Mapping[str, Any] | None) -> set[int]:
    if not record:
        return set()

    chats = record.get("chats", [])
    if isinstance(chats, Iterable) and not isinstance(chats, (str, bytes, bytearray)):
        try:
            return {int(chat_id) for chat_id in chats}
        except (TypeError, ValueError):
            pass

    return set(parse_chat_ids(chats))


async def _kick_from_chat(bot: Bot, user_id: int, chat_id: int) -> None:
    try:
        await bot.ban_chat_member(chat_id, user_id, until_date=0)
    except Exception as exc:  # pragma: no cover - network errors
        logger.error(f"[notifier] Не удалось исключить {user_id} из {chat_id}: {exc}")
        return

    with suppress(Exception):  # pragma: no cover - best effort
        await bot.unban_chat_member(chat_id, user_id)