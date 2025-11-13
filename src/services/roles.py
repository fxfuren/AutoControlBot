from storage.cache import cache


def get_user_by_tg_id(tg_id: int):
    return cache.get(str(tg_id))


def get_user_chats(tg_id: int):
    user = get_user_by_tg_id(tg_id)

    if not user:
        return []

    chats = user.get("chats")

    if chats is None:
        return []

    chats = str(chats).strip()

    if chats == "":
        return []

    if "," in chats:
        return [c.strip() for c in chats.split(",")]

    return [chats]
