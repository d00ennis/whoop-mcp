"""Kommandozeile: setup, auth, sync, serve, status."""

from __future__ import annotations

import argparse
import json
import sys
from getpass import getpass

from .config import SCOPES, export_path, load_credentials, redirect_uri, save_credentials


def cmd_setup(args) -> int:
    client_id = args.client_id or input("Client ID: ").strip()
    client_secret = args.client_secret or getpass("Client Secret: ").strip()
    if not client_id or not client_secret:
        print("Client ID und Client Secret werden beide benoetigt.", file=sys.stderr)
        return 1
    save_credentials(client_id, client_secret)
    print("Credentials gespeichert.")
    print(f"Redirect URL:  {redirect_uri()}")
    print(f"Scopes:        {' '.join(SCOPES)}")
    print("Naechster Schritt: whoop-mcp auth")
    return 0


def cmd_auth(args) -> int:
    from .auth import AuthError, authorize

    try:
        authorize(open_browser=not args.no_browser)
    except AuthError as exc:
        print(f"Authorisierung fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    print("Verbunden. Tokens sicher abgelegt.")
    return 0


def cmd_sync(args) -> int:
    from .sync import run

    result = run(days=args.days)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args) -> int:
    from .auth import TokenManager
    from .store import Store
    from .sync import LAST_SYNC_KEY

    try:
        load_credentials()
        creds_ok = True
    except RuntimeError:
        creds_ok = False

    authorized = False
    if creds_ok:
        try:
            authorized = TokenManager().is_authorized
        except Exception:
            authorized = False

    store = Store()
    print(json.dumps(
        {
            "credentials": creds_ok,
            "authorized": authorized,
            "redirect_uri": redirect_uri(),
            "database": str(store.path),
            "export": str(export_path()),
            "last_sync": store.get_meta(LAST_SYNC_KEY),
            "records": store.counts(),
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


def cmd_serve(args) -> int:
    from .server import main as serve

    serve()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="whoop-mcp", description="WHOOP MCP-Server")
    sub = parser.add_subparsers(dest="command", required=True)

    p_setup = sub.add_parser("setup", help="Client ID und Secret hinterlegen")
    p_setup.add_argument("--client-id")
    p_setup.add_argument("--client-secret")
    p_setup.set_defaults(func=cmd_setup)

    p_auth = sub.add_parser("auth", help="OAuth-Flow im Browser starten")
    p_auth.add_argument("--no-browser", action="store_true")
    p_auth.set_defaults(func=cmd_auth)

    p_sync = sub.add_parser("sync", help="Daten abrufen und lokal speichern")
    p_sync.add_argument("--days", type=int, default=None)
    p_sync.set_defaults(func=cmd_sync)

    sub.add_parser("status", help="Konfiguration und Datenbestand anzeigen").set_defaults(
        func=cmd_status
    )
    sub.add_parser("serve", help="MCP-Server starten (stdio)").set_defaults(func=cmd_serve)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
