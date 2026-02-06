from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator


# IMPORTANT:
# Эти имена начинаются с ctx_, чтобы не конфликтовать с logging.extra в коде
# (Python logging запрещает extra перезаписывать существующие атрибуты LogRecord).
ctx_request_id_var: ContextVar[str] = ContextVar("ctx_request_id", default="-")
ctx_update_id_var: ContextVar[str] = ContextVar("ctx_update_id", default="-")
ctx_user_id_var: ContextVar[str] = ContextVar("ctx_user_id", default="-")
ctx_chat_id_var: ContextVar[str] = ContextVar("ctx_chat_id", default="-")
ctx_meeting_id_var: ContextVar[str] = ContextVar("ctx_meeting_id", default="-")


def set_request_context(
    *,
    request_id: str | None = None,
    update_id: int | str | None = None,
    user_id: int | str | None = None,
    chat_id: int | str | None = None,
) -> list[Token]:
    tokens: list[Token] = []
    if request_id is not None:
        tokens.append(ctx_request_id_var.set(str(request_id)))
    if update_id is not None:
        tokens.append(ctx_update_id_var.set(str(update_id)))
    if user_id is not None:
        tokens.append(ctx_user_id_var.set(str(user_id)))
    if chat_id is not None:
        tokens.append(ctx_chat_id_var.set(str(chat_id)))
    return tokens


def reset_tokens(tokens: list[Token]) -> None:
    # tokens already know which var to reset
    for t in reversed(tokens):
        try:
            t.var.reset(t)
        except Exception:
            continue


@contextmanager
def bind_meeting_id(meeting_id: int | str | None) -> Iterator[None]:
    token = ctx_meeting_id_var.set(str(meeting_id) if meeting_id is not None else "-")
    try:
        yield
    finally:
        ctx_meeting_id_var.reset(token)


def get_logging_context() -> dict[str, str]:
    return {
        "ctx_request_id": ctx_request_id_var.get(),
        "ctx_update_id": ctx_update_id_var.get(),
        "ctx_user_id": ctx_user_id_var.get(),
        "ctx_chat_id": ctx_chat_id_var.get(),
        "ctx_meeting_id": ctx_meeting_id_var.get(),
    }

