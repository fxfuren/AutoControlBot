from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

from services.chat_utils import ensure_invite_link, get_chat
from services.ensure_user_can_join import ensure_user_can_join
from utils.logger import logger


async def chats_keyboard(bot: Bot, user_id: int, chats: list[int]):
    kb = InlineKeyboardBuilder()

    for chat_id in chats:
        await ensure_user_can_join(bot, user_id, chat_id)

        chat = await get_chat(bot, chat_id)
        if not chat:
            logger.warning("[buttons] Не удалось получить информацию о чате %s", chat_id)
            continue

        link = await ensure_invite_link(bot, chat_id, chat)
        if not link:
            logger.warning("[buttons] Не удалось получить ссылку-приглашение для чата %s", chat_id)
            continue

        title = chat.title or f"Чат {chat_id}"

        kb.button(text=title, url=link)

    kb.adjust(1)
    return kb.as_markup()