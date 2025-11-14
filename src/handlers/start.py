from contextlib import suppress
from aiogram import Router, types, Bot
from aiogram.filters import Command
from services.roles import get_user_by_tg_id, get_user_chats
from handlers.buttons import chats_keyboard

router = Router()

_start_messages = {}
_user_start_commands = {}


@router.message(Command("start"))
async def start_handler(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    user = get_user_by_tg_id(user_id)

    if not user:
        await message.answer("❌ У вас нет доступа.")
        return

    old_user_cmd = _user_start_commands.get(user_id)
    if old_user_cmd:
        with suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=old_user_cmd)

    old_bot_msg = _start_messages.get(user_id)
    if old_bot_msg:
        with suppress(Exception):
            await bot.delete_message(chat_id=chat_id, message_id=old_bot_msg)

    _user_start_commands[user_id] = message.message_id

    chats = get_user_chats(user_id)
    keyboard = await chats_keyboard(bot, user_id, chats)

    response = await message.answer(
        f"👋 Привет, {user.get('fio','пользователь')}!\n"
        "Вот ваши доступные чаты:",
        reply_markup=keyboard
    )

    _start_messages[user_id] = response.message_id
