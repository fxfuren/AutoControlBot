from __future__ import annotations

from contextlib import suppress
from typing import Optional

from aiogram import Bot, types
from aiogram.exceptions import TelegramAPIError

from src.utils.logger import logger


async def get_chat(bot: Bot, chat_id: int) -> Optional[types.Chat]:
    """
    Аккуратно получает объект чата.

    Возвращает:
        types.Chat — если чат успешно получен  
        None — если возникла ошибка (например, бот не имеет доступа)

    Ошибки Telegram API логируются, но не пробрасываются.
    """
    try:
        return await bot.get_chat(chat_id)
    except TelegramAPIError as exc:
        logger.error(
            f"[chat_utils] Не удалось получить чат {chat_id}: {exc}"
        )
        return None


async def ensure_invite_link(
    bot: Bot,
    chat_id: int,
    chat: types.Chat | None = None,
) -> Optional[str]:
    """
    Гарантированно возвращает рабочую ссылку-приглашение для чата.

    Логика:
    1. Если объект чата не передан — пытаемся получить его через get_chat().
    2. Если у чата уже есть постоянная invite_link — просто возвращаем её.
    3. Если ссылки нет — создаём новую через create_chat_invite_link().
    4. При ошибках API возвращается None, а ошибка логируется.

    Аргументы:
        bot (Bot): экземпляр aiogram бота.
        chat_id (int): ID чата.
        chat (types.Chat | None): опционально, уже полученный объект чата.

    Возвращает:
        str — invite-ссылка  
        None — если получить или создать ссылку не удалось
    """
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
            f"[chat_utils] Не удалось создать ссылку-приглашение для чата {chat_id}: {exc}"
        )
        return None

    return invite.invite_link


async def kick_user_from_chat(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Исключает пользователя из чата без перманентного бана."""
    try:
        await bot.ban_chat_member(chat_id, user_id, until_date=0)
    except TelegramAPIError as exc:
        logger.error(
            f"[chat_utils] Не удалось исключить пользователя {user_id} из чата {chat_id}: {exc}"
        )
        return False

    with suppress(TelegramAPIError):
        await bot.unban_chat_member(chat_id, user_id)

    return True