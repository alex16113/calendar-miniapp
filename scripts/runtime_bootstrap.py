from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

# чтобы `python scripts/runtime_bootstrap.py` видел модули из корня проекта
BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from config import load_settings
from logging_setup import setup_logging


logger = logging.getLogger(__name__)
RUNTIME_DIR = BASE_DIR / "runtime"


def _write_json_env(*, env_name: str, target_env_name: str, default_rel_path: str) -> Path | None:
    raw = os.getenv(env_name)
    if not raw:
        return None

    target = Path(os.getenv(target_env_name) or (BASE_DIR / default_rel_path))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in env", extra={"env": env_name})
        raise SystemExit(2)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote JSON secret to file", extra={"env": env_name, "path": str(target)})
    return target


def main() -> None:
    setup_logging()

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Runtime bootstrap started", extra={"runtime_dir": str(RUNTIME_DIR)})

    _write_json_env(
        env_name="GOOGLE_CREDENTIALS_JSON",
        target_env_name="GOOGLE_CREDENTIALS_PATH",
        default_rel_path="credentials.json",
    )
    _write_json_env(
        env_name="GOOGLE_OAUTH_CLIENT_SECRET_JSON",
        target_env_name="GOOGLE_OAUTH_CLIENT_SECRETS_PATH",
        default_rel_path="client_secrets.json",
    )
    _write_json_env(
        env_name="GOOGLE_OAUTH_TOKEN_JSON",
        target_env_name="GOOGLE_OAUTH_TOKEN_PATH",
        default_rel_path="token.json",
    )

    try:
        settings = load_settings()
    except Exception:
        logger.exception("Config validation failed during runtime bootstrap")
        raise SystemExit(2)

    if settings.google_auth_mode == "oauth":
        if not settings.oauth_client_secrets_path.is_file():
            logger.warning(
                "OAuth client_secrets.json not found after bootstrap",
                extra={"path": str(settings.oauth_client_secrets_path)},
            )
        if not settings.oauth_token_path.is_file():
            logger.warning(
                "OAuth token.json not found after bootstrap",
                extra={"path": str(settings.oauth_token_path)},
            )
    else:
        if not settings.credentials_path.is_file():
            logger.warning(
                "Service account credentials.json not found after bootstrap",
                extra={"path": str(settings.credentials_path)},
            )

    logger.info(
        "Runtime bootstrap finished",
        extra={"db_path": str(settings.db_path), "google_auth_mode": settings.google_auth_mode},
    )


if __name__ == "__main__":
    main()
