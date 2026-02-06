"""
Инициализация слоя доступа к SQLite.

Реэкспортируем основные функции из `database.py`, чтобы можно было писать:

    from database import init_db, get_db
"""

from .database import (  # noqa: F401
    Database,
    get_db,
    init_db,
)

