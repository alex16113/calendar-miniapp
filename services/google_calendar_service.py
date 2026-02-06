from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


DEFAULT_SCOPES: tuple[str, ...] = ("https://www.googleapis.com/auth/calendar",)


@dataclass(frozen=True)
class AuthNeeded(Exception):
    authorization_url: str

    def __str__(self) -> str:  # pragma: no cover
        return f"OAuth authorization required. Open: {self.authorization_url}"


class GoogleCalendarService:
    """
    OAuth 2.0 (Desktop app) авторизация для Google Calendar.

    Управляет token.json:
    - загрузка
    - refresh при истечении
    - сохранение
    - генерация authorization URL, если токена нет/refresh невозможен
    """

    def __init__(
        self,
        *,
        client_secrets_path: Path | str,
        token_path: Path | str,
        scopes: Iterable[str] = DEFAULT_SCOPES,
    ) -> None:
        self._client_secrets_path = Path(client_secrets_path)
        self._token_path = Path(token_path)
        self._scopes = tuple(scopes)

    @property
    def token_path(self) -> Path:
        return self._token_path

    @property
    def client_secrets_path(self) -> Path:
        return self._client_secrets_path

    def load_credentials(self) -> Credentials | None:
        if not self._token_path.is_file():
            return None
        try:
            creds = Credentials.from_authorized_user_file(str(self._token_path), scopes=list(self._scopes))
        except Exception:
            logger.exception("Failed to load token.json", extra={"token_path": str(self._token_path)})
            return None
        return creds

    def save_credentials(self, creds: Credentials) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(creds.to_json(), encoding="utf-8")

    def get_authorization_url(self) -> str:
        if not self._client_secrets_path.is_file():
            raise FileNotFoundError(f"OAuth client secrets not found: {self._client_secrets_path}")

        flow = InstalledAppFlow.from_client_secrets_file(str(self._client_secrets_path), scopes=list(self._scopes))
        url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return url

    def ensure_valid_credentials(self) -> Credentials:
        creds = self.load_credentials()
        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing Google OAuth token", extra={"token_path": str(self._token_path)})
            try:
                creds.refresh(Request())
            except Exception:
                logger.exception("Google OAuth token refresh failed", extra={"token_path": str(self._token_path)})
            else:
                self.save_credentials(creds)
                return creds

        # Токена нет или refresh невозможен — нужен интерактивный логин.
        url = self.get_authorization_url()
        raise AuthNeeded(authorization_url=url)

    def build_service(self) -> Any:
        creds = self.ensure_valid_credentials()
        logger.info(
            "Initializing Google Calendar OAuth client",
            extra={
                "client_secrets_path": str(self._client_secrets_path),
                "token_path": str(self._token_path),
                "scopes": list(self._scopes),
            },
        )
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def try_print_auth_hint(self) -> str | None:
        """
        Возвращает URL, если нужна авторизация. Ничего не бросает наружу — удобно для старта бота.
        """
        try:
            _ = self.ensure_valid_credentials()
            return None
        except AuthNeeded as e:
            return e.authorization_url
        except FileNotFoundError:
            # Если секретов нет — просто молча сигнализируем (на проде может быть SA fallback).
            logger.warning("OAuth client_secrets.json not found; cannot init OAuth", extra={"path": str(self._client_secrets_path)})
            return None

