from collections import OrderedDict
from contextlib import suppress

from aiogram import Bot, Router, types
from aiogram.filters import Command

from handlers.chats_buttons import chats_keyboard
from services.container import get_container

router = Router()

# LRU-like dictionaries with size limit to prevent unbounded memory growth
_MAX_CACHE_SIZE = 1000
_start_messages = OrderedDict()
_user_start_commands = OrderedDict()


def _limit_dict_size(d: OrderedDict, max_size: int = _MAX_CACHE_SIZE) -> None:
    """Remove oldest entries if dictionary exceeds max_size."""
    while len(d) > max_size:
        d.popitem(last=False)


@router.message(Command("start"))
async def start_handler(message: types.Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id

    services = get_container()
    access_service = services.access

    user = access_service.get_user(user_id)

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
    _limit_dict_size(_user_start_commands)

    chat_links = await access_service.resolve_chat_access(bot, user_id)
    keyboard = chats_keyboard(chat_links)

    text = "Вот ваши доступные чаты:" if chat_links else "🔐 У вас пока нет доступных чатов"
    response = await message.answer(text, reply_markup=keyboard)

    _start_messages[user_id] = response.message_id
    _limit_dict_size(_start_messages)