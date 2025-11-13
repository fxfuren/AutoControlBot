from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram import Bot

async def chats_keyboard(bot: Bot, chats: list[str]):
    kb = InlineKeyboardBuilder()

    for chat_id in chats:
        try:
            chat_id_int = int(chat_id)
            link = await bot.create_chat_invite_link(chat_id_int)

            kb.button(
                text=f"Чат {chat_id}",
                url=link.invite_link
            )

        except Exception as e:
            print(f"[ERROR] Chat ID {chat_id} → {e}")

    kb.adjust(1)
    return kb.as_markup()
