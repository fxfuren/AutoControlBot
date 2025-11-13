from aiogram import Router, types, Bot
from aiogram.filters import Command

from services.roles import get_user_by_tg_id, get_user_chats
from handlers.buttons import chats_keyboard

router = Router()


@router.message(Command("start"))
async def start_handler(message: types.Message, bot: Bot):
    user = get_user_by_tg_id(message.from_user.id)

    if not user:
        await message.answer("❌ У вас нет доступа.")
        return

    chats = get_user_chats(message.from_user.id)
    keyboard = await chats_keyboard(bot, chats)

    await message.answer(
        f"👋 Привет, {user.get('fio','пользователь')}!\n"
        "Вот ваши доступные чаты:",
        reply_markup=keyboard
    )
