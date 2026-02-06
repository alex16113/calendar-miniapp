from __future__ import annotations

import logging
import os
from typing import Optional

from logging_context import get_logging_context


def setup_logging(level: Optional[str] = None) -> None:
    """
    Единая настройка логирования для всего проекта.

    Уровень берётся из аргумента или из env `LOG_LEVEL` (по умолчанию INFO).
    """
    effective_level = (level or os.getenv("LOG_LEVEL") or "INFO").upper()

    # Глобально подмешиваем контекстные поля в каждый LogRecord.
    # Это надёжнее фильтров: поля гарантированно существуют до форматирования.
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        record = old_factory(*args, **kwargs)
        ctx = get_logging_context()
        for k, v in ctx.items():
            if not hasattr(record, k):
                setattr(record, k, v)
        return record

    logging.setLogRecordFactory(record_factory)

    logging.basicConfig(
        level=effective_level,
        format=(
            "%(asctime)s | %(levelname)s | req=%(ctx_request_id)s | upd=%(ctx_update_id)s | "
            "user=%(ctx_user_id)s | chat=%(ctx_chat_id)s | meeting=%(ctx_meeting_id)s | %(name)s | %(message)s"
        ),
    )

