#!/usr/bin/env python3
"""
Генерация валидного initData для теста API (локально).
Использовать только для отладки: подставь в заголовок X-Telegram-Init-Data.

  python scripts/gen_init_data.py USER_ID
  python scripts/gen_init_data.py 123456789

Затем:
  curl -s -H "X-Telegram-Init-Data: <вставь вывод>" http://localhost:8000/my/meetings
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from urllib.parse import urlencode

# загружаем конфиг из корня проекта
from pathlib import Path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
from config import load_settings


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/gen_init_data.py USER_ID", file=sys.stderr)
        sys.exit(1)
    user_id = int(sys.argv[1])
    settings = load_settings()
    auth_date = int(time.time())
    user_json = json.dumps({
        "id": user_id,
        "first_name": "Test",
        "last_name": "",
        "username": "test_user",
    }, separators=(",", ":"))
    params = {"auth_date": str(auth_date), "user": user_json}
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(
        settings.bot_token.encode(),
        b"WebAppData",
        hashlib.sha256,
    ).digest()
    h = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    params["hash"] = h
    init_data = urlencode(params, safe="")
    print(init_data)


if __name__ == "__main__":
    main()
