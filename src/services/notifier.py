import html
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from aiogram import Bot
from utils.logger import logger


@dataclass(slots=True)
class UserChangeEvent:
    tg_id: int
    changed_role: Optional[tuple[str, str]] = None
    new_chats: List[int] = field(default_factory=list)
    removed_chats: List[int] = field(default_factory=list)


class NotificationBuilder:

    async def build(self, bot: Bot, event: UserChangeEvent) -> Optional[str]:
        lines: List[str] = ["<b>🔔 Обновление доступа</b>"]
        chat_titles: dict[int, Optional[str]] = {}

        async def _title(chat_id: int) -> Optional[str]:
            if chat_id not in chat_titles:
                try:
                    chat = await bot.get_chat(chat_id)
                    chat_titles[chat_id] = chat.title
                except Exception:
                    chat_titles[chat_id] = None
            return chat_titles[chat_id]

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
                try:
                    chat = await bot.get_chat(chat_id)
                    invite = chat.invite_link  # << ТЕПЕРЬ ТАК
                except Exception as exc:
                    logger.error(f"[notifier] Ошибка получения invite_link для {chat_id}: {exc}")
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


async def _kick_from_chat(bot: Bot, user_id: int, chat_id: int) -> None:
    try:
        await bot.ban_chat_member(chat_id, user_id, until_date=0)
    except Exception as exc:
        logger.error(f"[notifier] Не удалось исключить {user_id} из {chat_id}: {exc}")
        return

    with suppress(Exception):
        await bot.unban_chat_member(chat_id, user_id)
