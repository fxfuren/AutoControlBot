from __future__ import annotations

import html
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from aiogram import Bot

from services.invite_links import InviteLinkManager
from utils.logger import logger


@dataclass(slots=True)
class UserChangeEvent:
    tg_id: int
    changed_role: Optional[tuple[str, str]] = None
    new_chats: List[int] = field(default_factory=list)
    removed_chats: List[int] = field(default_factory=list)


class NotificationBuilder:
    """Builds nicely formatted notifications for the user."""

    def __init__(self, invite_manager: InviteLinkManager | None = None) -> None:
        self._invite_manager = invite_manager or InviteLinkManager()

    async def build(self, bot: Bot, event: UserChangeEvent) -> Optional[str]:
        lines: List[str] = ["<b>🔔 Обновление доступа</b>"]
        chat_titles: dict[int, Optional[str]] = {}

        async def _title(chat_id: int) -> Optional[str]:
            if chat_id not in chat_titles:
                chat_titles[chat_id] = await _safe_chat_title(bot, chat_id)
            return chat_titles[chat_id]

        if event.changed_role:
            old_role, new_role = (html.escape(part) for part in event.changed_role)
            lines.extend(
                [
                    "\n🎭 <b>Изменение роли</b>",
                    f"• Было: <code>{old_role or '-'}</code>",
                    f"• Стало: <code>{new_role or '-'}</code>",
                ]
            )

        if event.new_chats:
            lines.append("\n📥 <b>Доступ к новым чатам</b>")
            for chat_id in event.new_chats:
                try:
                    invite = await self._invite_manager.get_link(bot, event.tg_id, chat_id)
                except Exception as exc:  # pragma: no cover - runtime only
                    logger.error(f"[notifier] Ошибка создания ссылки для {chat_id}: {exc}")
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
                with suppress(Exception):  # pragma: no cover - runtime only
                    await self._invite_manager.reset_link(event.tg_id, chat_id)

        if len(lines) == 1:
            return None

        return "\n".join(lines)


async def _safe_chat_title(bot: Bot, chat_id: int) -> Optional[str]:
    try:
        chat = await bot.get_chat(chat_id)
        return chat.title
    except Exception:  # pragma: no cover - relies on Telegram API at runtime
        return None


def parse_chats(chats):
    """Строку 'id1, id2' → ['id1', 'id2']"""
    if not chats:
        return []

    if isinstance(chats, str):
        return [c.strip() for c in chats.split(",") if c.strip()]

    return chats


def detect_changes(old_data: dict, new_data: dict) -> List[UserChangeEvent]:
    events: List[UserChangeEvent] = []

    for user_id, new_user in new_data.items():
        old_user = old_data.get(user_id)

        if not old_user:
            continue

        user_event = UserChangeEvent(tg_id=int(user_id))

        old_role = old_user.get("role", "")
        new_role = new_user.get("role", "")

        if old_role != new_role:
            user_event.changed_role = (str(old_role), str(new_role))

        old_chats = _normalize_chat_ids(parse_chats(old_user.get("chats", "")))
        new_chats = _normalize_chat_ids(parse_chats(new_user.get("chats", "")))

        added = sorted(new_chats - old_chats)
        removed = sorted(old_chats - new_chats)

        if added:
            user_event.new_chats = added

        if removed:
            user_event.removed_chats = removed

        if user_event.changed_role or user_event.new_chats or user_event.removed_chats:
            events.append(user_event)

    return events


def _normalize_chat_ids(chats: Iterable[str | int]) -> set[int]:
    result: set[int] = set()
    for chat in chats:
        try:
            result.add(int(chat))
        except (TypeError, ValueError):
            logger.warning(f"[notifier] Не удалось преобразовать идентификатор чата: {chat}")
    return result


class NotificationService:
    """Facade responsible for sending change notifications to users."""

    def __init__(self, bot: Bot, builder: NotificationBuilder | None = None) -> None:
        self._bot = bot
        self._builder = builder or NotificationBuilder()

    async def notify(self, event: UserChangeEvent) -> None:
        message = await self._builder.build(self._bot, event)
        if not message:
            return

        try:
            await self._bot.send_message(event.tg_id, message, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as exc:  # pragma: no cover - runtime only
            logger.error(f"[notifier] Ошибка отправки уведомления {event.tg_id}: {exc}")


async def notify_user(bot: Bot, event: UserChangeEvent) -> None:
    """Backward compatibility wrapper."""
    service = NotificationService(bot)
    await service.notify(event)