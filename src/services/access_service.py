from __future__ import annotations

from dataclasses import dataclass
from typing import List

from aiogram import Bot

from services.chat_utils import ensure_invite_link, get_chat
from services.ensure_user_can_join import ensure_user_can_join
from storage.cache import CacheRepository
from utils.logger import logger


@dataclass(slots=True)
class ChatAccess:
    chat_id: int
    title: str
    invite_link: str


class AccessService:
    """Сервис доменной логики работы с доступами пользователей."""

    def __init__(self, cache: CacheRepository) -> None:
        self._cache = cache

    def get_user(self, tg_id: int):
        return self._cache.get_user(tg_id)

    def list_chat_ids(self, tg_id: int) -> list[int]:
        return self._cache.list_user_chats(tg_id)

    async def resolve_chat_access(self, bot: Bot, tg_id: int) -> List[ChatAccess]:
        """Возвращает список чатов с готовыми инвайтами для пользователя."""
        result: List[ChatAccess] = []
        for chat_id in self.list_chat_ids(tg_id):
            await ensure_user_can_join(bot, tg_id, chat_id)

            chat = await get_chat(bot, chat_id)
            if not chat:
                logger.warning(f"[access_service] Не удалось получить чат {chat_id}")
                continue

            invite_link = await ensure_invite_link(bot, chat_id, chat)
            if not invite_link:
                logger.warning(
                    f"[access_service] Не удалось получить ссылку-приглашение {chat_id}"
                )
                continue

            title = chat.title or f"Чат {chat_id}"
            result.append(ChatAccess(chat_id=chat_id, title=title, invite_link=invite_link))
        return result