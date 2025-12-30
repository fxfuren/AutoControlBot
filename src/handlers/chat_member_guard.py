from aiogram import Bot, Router, types
from aiogram.enums import ChatMemberStatus

from src.services.chat_utils import kick_user_from_chat
from src.services.container import get_container
from src.utils.logger import logger

router = Router()


@router.chat_member()
async def guard_chat_member(event: types.ChatMemberUpdated, bot: Bot) -> None:
    """Проверяет новых участников чата и удаляет тех, кого нет в таблице."""
    if not _is_new_member(event):
        return

    user = event.new_chat_member.user
    if not user or user.is_bot:
        return

    chat_id = event.chat.id
    services = get_container()
    access_service = services.access

    if not access_service.is_managed_chat(chat_id):
        return

    if access_service.user_has_access_to_chat(user.id, chat_id):
        logger.info(
            f"[chat_guard] {user.full_name} ({user.id}) присоединился к {chat_id} — доступ подтверждён"
        )
        return

    kicked = await kick_user_from_chat(bot, chat_id, user.id)
    if kicked:
        logger.info(
            f"[chat_guard] {user.full_name} ({user.id}) исключён из {chat_id} — пользователя нет в таблице"
        )
    else:
        logger.warning(
            f"[chat_guard] Не удалось исключить {user.full_name} ({user.id}) из {chat_id}"
        )


def _is_new_member(event: types.ChatMemberUpdated) -> bool:
    new_status = event.new_chat_member.status
    old_status = event.old_chat_member.status

    if new_status != ChatMemberStatus.MEMBER:
        return False

    return new_status != old_status