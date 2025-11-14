"""Helpers for retrieving chat metadata and invite links."""
from __future__ import annotations

from typing import Optional

from aiogram import Bot, types
from aiogram.exceptions import TelegramAPIError

from utils.logger import logger


async def get_chat(bot: Bot, chat_id: int) -> Optional[types.Chat]:
    """Fetch chat information, logging errors instead of raising."""

    try:
        return await bot.get_chat(chat_id)
    except TelegramAPIError as exc:
        logger.error("[chat_utils] Не удалось получить чат %s: %s", chat_id, exc)
        return None


async def ensure_invite_link(
    bot: Bot, chat_id: int, chat: types.Chat | None = None
) -> Optional[str]:
    """Return an invite link for a chat, creating one if required."""

    if chat is None:
        chat = await get_chat(bot, chat_id)
        if chat is None:
            return None

    if chat.invite_link:
        return chat.invite_link

    try:
        invite = await bot.create_chat_invite_link(chat_id)
    except TelegramAPIError as exc:
        logger.error(
            "[chat_utils] Не удалось создать ссылку-приглашение для чата %s: %s",
            chat_id,
            exc,
        )
        return None

    return invite.invite_link