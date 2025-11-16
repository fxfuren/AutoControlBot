from typing import Sequence

from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.access_service import ChatAccess


def chats_keyboard(chats: Sequence[ChatAccess]):
    kb = InlineKeyboardBuilder()

    for chat in chats:
        kb.button(text=chat.title, url=chat.invite_link)

    kb.adjust(1)
    return kb.as_markup()