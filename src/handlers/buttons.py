from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot
from services.ensure_user_can_join import ensure_user_can_join


async def chats_keyboard(bot: Bot, user_id: int, chats: list[str]):
    kb = InlineKeyboardBuilder()

    for chat_id in chats:
        chat_id_int = int(chat_id)

        # снимаем бан/кик
        await ensure_user_can_join(bot, user_id, chat_id_int)

        chat = await bot.get_chat(chat_id_int)
        title = chat.title or f"Чат {chat_id}"

        link = chat.invite_link   # ← ГЛАВНЫЙ МОМЕНТ

        kb.button(text=title, url=link)

    kb.adjust(1)
    return kb.as_markup()
