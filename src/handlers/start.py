from collections import OrderedDict
from contextlib import suppress

from aiogram import Bot, Router, types
from aiogram.filters import Command

from src.handlers.chats_buttons import chats_keyboard
from src.services.container import get_container

router = Router()

# Ограничиваем размер словарей для предотвращения утечки памяти
MAX_CACHED_USERS = 1000
_start_messages: OrderedDict[int, int] = OrderedDict()
_user_start_commands: OrderedDict[int, int] = OrderedDict()


def _add_to_cache(cache: OrderedDict, key: int, value: int) -> None:
    """Добавляет запись в кэш с автоматической очисткой старых записей."""
    if key in cache:
        cache.move_to_end(key)
    cache[key] = value
    if len(cache) > MAX_CACHED_USERS:
        cache.popitem(last=False)  # Удаляем самую старую запись


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

    _add_to_cache(_user_start_commands, user_id, message.message_id)

    chat_links = await access_service.resolve_chat_access(bot, user_id)
    keyboard = chats_keyboard(chat_links)

    text = "Вот ваши доступные чаты:" if chat_links else "🔐 У вас пока нет доступных чатов"
    response = await message.answer(text, reply_markup=keyboard)

    _add_to_cache(_start_messages, user_id, response.message_id)