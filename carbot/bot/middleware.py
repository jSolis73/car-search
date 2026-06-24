from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message


class OwnerMiddleware(BaseMiddleware):
    def __init__(self, owner_chat_id: int):
        self._owner_id = owner_chat_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message):
            if event.chat.id != self._owner_id:
                return  # silently ignore
        return await handler(event, data)
