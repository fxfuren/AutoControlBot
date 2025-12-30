from __future__ import annotations

from dataclasses import dataclass
from typing import List

from aiogram import Bot

from src.services.chat_utils import ensure_invite_link, get_chat
from src.services.ensure_user_can_join import ensure_user_can_join
from src.storage.cache import CacheRepository
from src.utils.logger import logger


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

    def user_has_access_to_chat(self, tg_id: int, chat_id: int) -> bool:
        """Возвращает True, если пользователь имеет доступ к указанному чату."""
        return self._cache.user_has_access(tg_id, chat_id)

    def is_managed_chat(self, chat_id: int) -> bool:
        """Проверяет, присутствует ли чат в таблице доступов."""
        return self._cache.chat_is_managed(chat_id)

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