from aiogram import Bot
from aiogram.enums import ChatMemberStatus


async def ensure_user_can_join(bot: Bot, user_id: int, chat_id: int):
    """Снимает бан/кик перед выдачей ссылки."""
    try:
        member = await bot.get_chat_member(chat_id, user_id)

        if member.status in {ChatMemberStatus.BANNED, ChatMemberStatus.KICKED}:
            await bot.unban_chat_member(chat_id, user_id)

    except Exception:
        pass
