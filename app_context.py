from __future__ import annotations

from config import Settings, load_settings


_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Лениво загружаем Settings один раз за процесс.
    """
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings

