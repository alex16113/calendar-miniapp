from __future__ import annotations

import argparse
import sys
from pathlib import Path

# чтобы `python scripts/google_oauth_init.py` видел модули из корня проекта
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import load_settings
from logging_setup import setup_logging
from services.google_calendar_service import DEFAULT_SCOPES, GoogleCalendarService


def main() -> None:
    setup_logging()
    s = load_settings()

    parser = argparse.ArgumentParser(description="Initialize Google OAuth token.json for Smart Scheduler")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Do not start local server. Print URL and ask for code paste.",
    )
    args = parser.parse_args()

    oauth = GoogleCalendarService(
        client_secrets_path=s.oauth_client_secrets_path,
        token_path=s.oauth_token_path,
        scopes=DEFAULT_SCOPES,
    )

    if oauth.token_path.is_file():
        print(f"token already exists: {oauth.token_path}")
        print("If you want to re-auth, delete token.json and run again.")
        return

    if args.manual:
        url = oauth.get_authorization_url()
        print("Open this URL in your browser and complete authorization:")
        print(url)
        code = input("Paste the authorization code here: ").strip()

        # Minimal manual flow: reuse InstalledAppFlow logic directly.
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(oauth.client_secrets_path), scopes=list(DEFAULT_SCOPES))
        flow.fetch_token(code=code)
        creds = flow.credentials
        oauth.save_credentials(creds)
        print(f"OK: token saved to {oauth.token_path}")
        return

    # Preferred: local loopback server (opens browser automatically).
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(oauth.client_secrets_path), scopes=list(DEFAULT_SCOPES))
    creds = flow.run_local_server(port=0)
    oauth.save_credentials(creds)
    print(f"OK: token saved to {oauth.token_path}")


if __name__ == "__main__":
    main()

