from __future__ import annotations

import sys
from pathlib import Path

# чтобы `python scripts/init_db.py` видел модули из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings
from database import init_db
from logging_setup import setup_logging


def main() -> None:
    setup_logging()
    s = load_settings()

    db = init_db(s.db_path)
    inserted = db.bootstrap_settings(
        timezone=s.timezone,
        work_start=s.work_start,
        work_end=s.work_end,
        buffer_hours=s.buffer_hours,
    )

    print("OK")
    print(f"DB_PATH={s.db_path}")
    print(f"inserted_defaults={inserted}")


if __name__ == "__main__":
    main()

