from __future__ import annotations

import logging
from uuid import uuid4

from aiogram.dispatcher.middlewares.base import BaseMiddleware

from logging_context import reset_tokens, set_request_context


logger = logging.getLogger(__name__)


class LogContextMiddleware(BaseMiddleware):
    """
    Сквозной лог-контекст на каждый update:
    - request_id (короткий)
    - update_id
    - user_id
    - chat_id
    """

    async def __call__(self, handler, event, data):  # type: ignore[override]
        request_id = uuid4().hex[:12]

        update = data.get("event_update")
        update_id = getattr(update, "update_id", None)

        from_user = data.get("event_from_user") or getattr(event, "from_user", None)
        user_id = getattr(from_user, "id", None)

        chat = data.get("event_chat") or getattr(event, "chat", None)
        chat_id = getattr(chat, "id", None)

        tokens = set_request_context(
            request_id=request_id,
            update_id=update_id,
            user_id=user_id,
            chat_id=chat_id,
        )
        try:
            return await handler(event, data)
        finally:
            reset_tokens(tokens)

