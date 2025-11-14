from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.enums import ChatMemberStatus

from utils.json_store import JsonKeyValueStore
from utils.logger import logger

_INVITE_LINKS_PATH = Path("src/storage/invite_links.json")


@dataclass(slots=True)
class StoredInviteLink:
    chat_id: int
    user_id: int
    link: str
    expires_at: Optional[int] = None

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "link": self.link,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | int | None]) -> "StoredInviteLink":
        return cls(
            chat_id=int(data["chat_id"]),
            user_id=int(data["user_id"]),
            link=str(data["link"]),
            expires_at=int(data["expires_at"]) if data.get("expires_at") is not None else None,
        )

    @classmethod
    def from_invite(cls, user_id: int, chat_id: int, invite) -> "StoredInviteLink":
        expires_at: Optional[int] = None
        expire_date = getattr(invite, "expire_date", None)
        if expire_date:
            if isinstance(expire_date, datetime):
                if expire_date.tzinfo is None:
                    expire_date = expire_date.replace(tzinfo=timezone.utc)
                else:
                    expire_date = expire_date.astimezone(timezone.utc)
                expires_at = int(expire_date.timestamp())
            else:  # Telegram may already return timestamp
                expires_at = int(expire_date)
        return cls(chat_id=chat_id, user_id=user_id, link=str(invite.invite_link), expires_at=expires_at)

    def is_expired(self, *, now: Optional[datetime] = None) -> bool:
        if self.expires_at is None:
            return False
        moment = now or datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        return self.expires_at <= int(moment.timestamp())


class InviteLinkManager:
    """Coordinates creation and reuse of invite links.

    Acts as a mini-facade over the JSON store. The manager reuses the invite
    link for a specific (user, chat) pair until we explicitly reset it. If the
    link becomes invalid Telegram will raise an exception — in that case we
    automatically create a new link and overwrite the stored value.
    """

    def __init__(self, storage: Optional[JsonKeyValueStore] = None) -> None:
        self._storage = storage or JsonKeyValueStore(_INVITE_LINKS_PATH)
        self._lock = asyncio.Lock()

    def _key(self, user_id: int, chat_id: int) -> str:
        return f"{user_id}:{chat_id}"

    async def get_link(self, bot: Bot, user_id: int, chat_id: int) -> str:
        key = self._key(user_id, chat_id)

        async with self._lock:
            stored = await self._storage.get(key)
            if stored:
                stored_link = StoredInviteLink.from_dict(stored)
                if await self._can_reuse(bot, stored_link):
                    return stored_link.link

            new_link = await self._create_link(bot, user_id, chat_id)
            await self._storage.set(key, new_link.as_dict())
            return new_link.link

    async def reset_link(self, user_id: int, chat_id: int) -> None:
        await self._storage.delete(self._key(user_id, chat_id))

    async def _create_link(self, bot: Bot, user_id: int, chat_id: int) -> StoredInviteLink:
        try:
            invite = await bot.create_chat_invite_link(
                chat_id,
                member_limit=1,  
                expire_date=None     # бессрочная
            )
            return StoredInviteLink.from_invite(user_id, chat_id, invite)

        except Exception as exc:
            logger.error(
                f"Не удалось создать ссылку-приглашение для чата {chat_id}: {exc}"
            )
            raise

    async def _can_reuse(self, bot: Bot, stored: StoredInviteLink) -> bool:
        if stored.is_expired():
            return False

        used = await self._was_used(bot, stored)
        return not used

    async def _was_used(self, bot: Bot, stored: StoredInviteLink) -> bool:
        try:
            member = await bot.get_chat_member(stored.chat_id, stored.user_id)
        except Exception as exc:  # pragma: no cover - runtime only
            logger.debug(
                "[invite] Не удалось получить статус пользователя %s в чате %s: %s",
                stored.user_id,
                stored.chat_id,
                exc,
            )
            return False

        return member.status in {
            ChatMemberStatus.CREATOR,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.RESTRICTED,
        }