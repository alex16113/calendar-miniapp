from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class BookingFSM(StatesGroup):
    duration = State()
    date = State()
    time = State()
    name = State()
    subject = State()
    description = State()
    email = State()


class ModerationFSM(StatesGroup):
    reject_reason = State()


class AdminFSM(StatesGroup):
    timezone = State()
    work_hours = State()
    work_hours_day = State()
    buffer_hours = State()
    blacklist_add = State()
    blacklist_remove = State()
    broadcast_date = State()
    broadcast_text = State()

