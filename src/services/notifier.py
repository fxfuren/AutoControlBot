from utils.logger import logger


def parse_chats(chats):
    """Строку 'id1, id2' → ['id1', 'id2']"""
    if not chats:
        return []

    if isinstance(chats, str):
        return [c.strip() for c in chats.split(",") if c.strip()]

    return chats


def detect_changes(old_data: dict, new_data: dict):
    events = []

    for user_id, new_user in new_data.items():
        old_user = old_data.get(user_id)

        if not old_user:
            continue

        user_events = {
            "tg_id": int(user_id),
            "changed_role": None,
            "new_chats": [],
            "removed_chats": []
        }

        # ---------- ROLE ----------
        old_role = old_user.get("role", "")
        new_role = new_user.get("role", "")

        if old_role != new_role:
            user_events["changed_role"] = (old_role, new_role)

        # ---------- CHATS ----------
        old_chats = set(parse_chats(old_user.get("chats", "")))
        new_chats = set(parse_chats(new_user.get("chats", "")))

        added = list(new_chats - old_chats)
        removed = list(old_chats - new_chats)

        if added:
            user_events["new_chats"] = added

        if removed:
            user_events["removed_chats"] = removed

        # Добавляем только если есть что отправлять
        if (user_events["changed_role"] or
            user_events["new_chats"] or
            user_events["removed_chats"]):
            events.append(user_events)

    return events



async def notify_user(bot, event):
    tg_id = event["tg_id"]

    # ROLE
    if event["changed_role"]:
        old_role, new_role = event["changed_role"]
        text = (
            f"🔔 *Ваша роль обновлена!*\n\n"
            f"*Было:* `{old_role}`\n"
            f"*Стало:* `{new_role}`"
        )
        try:
            await bot.send_message(tg_id, text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[notifier] Ошибка отправки роли {tg_id}: {e}")

    # NEW CHATS
    for chat_id in event["new_chats"]:
        try:
            link = await bot.create_chat_invite_link(int(chat_id))
            text = f"🆕 Вам выдан доступ к новому чату:\n{link.invite_link}"
            await bot.send_message(tg_id, text)
        except Exception as e:
            logger.error(f"[notifier] Ошибка нового чата {tg_id}: {e}")

    # REMOVED CHATS
    for chat_id in event["removed_chats"]:
        try:
            text = f"❗ Вам был *удалён доступ* к чату `{chat_id}`"
            await bot.send_message(tg_id, text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"[notifier] Ошибка удаления чата {tg_id}: {e}")

