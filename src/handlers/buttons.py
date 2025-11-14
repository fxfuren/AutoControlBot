from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot
from datetime import datetime, timedelta


async def chats_keyboard(bot: Bot, chats: list[str]):
    kb = InlineKeyboardBuilder()

    for chat_id in chats:
        try:
            chat_id_int = int(chat_id)

            # Получаем объект чата → у него есть .title
            chat = await bot.get_chat(chat_id_int)
            chat_title = chat.title or f"Чат {chat_id}"

            # Создаем ссылку (без expire_date, тк иначе ошибка)
            link = await bot.create_chat_invite_link(
                chat_id_int,
                member_limit=1   # одноразовая (но не одно-вступление!)
            )

            kb.button(
                text=chat_title,
                url=link.invite_link
            )

        except Exception as e:
            print(f"[ERROR] Chat ID {chat_id} → {e}")

    kb.adjust(1)
    return kb.as_markup()
