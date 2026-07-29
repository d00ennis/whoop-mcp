"""Konfiguration und sichere Ablage von Credentials.

Primaerer Speicher ist der macOS-Schluesselbund (via ``keyring``). Wenn kein
Keyring verfuegbar ist -- etwa in CI oder in einem Container -- faellt der
Speicher auf eine Datei mit Zugriffsmodus 0600 zurueck.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

SERVICE = "whoop-mcp"

AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
API_BASE = "https://api.prod.whoop.com/developer"

DEFAULT_REDIRECT_URI = "http://localhost:8765/callback"

# "offline" ist zwingend erforderlich, sonst liefert WHOOP keinen Refresh Token.
SCOPES = [
    "offline",
    "read:recovery",
    "read:cycles",
    "read:sleep",
    "read:workout",
    "read:body_measurement",
    "read:profile",
]


def data_dir() -> Path:
    """Verzeichnis fuer Datenbank, Exporte und Fallback-Secrets."""
    override = os.environ.get("WHOOP_MCP_DATA_DIR")
    if override:
        path = Path(override)
    else:
        path = Path.home() / ".whoop-mcp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "whoop.db"


def export_path() -> Path:
    override = os.environ.get("WHOOP_MCP_EXPORT_PATH")
    return Path(override) if override else data_dir() / "whoop.json"


def redirect_uri() -> str:
    return os.environ.get("WHOOP_REDIRECT_URI", DEFAULT_REDIRECT_URI)


class SecretStore:
    """Key/Value-Speicher fuer Secrets, Keyring mit Datei-Fallback."""

    def __init__(self, service: str = SERVICE, fallback: Path | None = None):
        self.service = service
        self._fallback = fallback or (data_dir() / "secrets.json")
        self._keyring = self._load_keyring()

    @staticmethod
    def _load_keyring():
        if os.environ.get("WHOOP_MCP_NO_KEYRING"):
            return None
        try:
            import keyring

            keyring.get_keyring()
            return keyring
        except Exception:
            return None

    def get(self, key: str) -> str | None:
        if self._keyring is not None:
            try:
                return self._keyring.get_password(self.service, key)
            except Exception:
                pass
        return self._read_fallback().get(key)

    def set(self, key: str, value: str) -> None:
        if self._keyring is not None:
            try:
                self._keyring.set_password(self.service, key, value)
                return
            except Exception:
                pass
        data = self._read_fallback()
        data[key] = value
        self._write_fallback(data)

    def delete(self, key: str) -> None:
        if self._keyring is not None:
            try:
                self._keyring.delete_password(self.service, key)
            except Exception:
                pass
        data = self._read_fallback()
        if data.pop(key, None) is not None:
            self._write_fallback(data)

    def _read_fallback(self) -> dict:
        if not self._fallback.exists():
            return {}
        try:
            return json.loads(self._fallback.read_text())
        except (ValueError, OSError):
            return {}

    def _write_fallback(self, data: dict) -> None:
        self._fallback.parent.mkdir(parents=True, exist_ok=True)
        self._fallback.write_text(json.dumps(data, indent=2))
        self._fallback.chmod(0o600)


@dataclass(frozen=True)
class ClientCredentials:
    client_id: str
    client_secret: str


def load_credentials(store: SecretStore | None = None) -> ClientCredentials:
    """Client ID/Secret aus Umgebung oder Secret-Store lesen."""
    store = store or SecretStore()
    client_id = os.environ.get("WHOOP_CLIENT_ID") or store.get("client_id")
    client_secret = os.environ.get("WHOOP_CLIENT_SECRET") or store.get("client_secret")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Keine WHOOP-Credentials hinterlegt. Bitte zuerst 'whoop-mcp setup' ausfuehren."
        )
    return ClientCredentials(client_id=client_id, client_secret=client_secret)


def save_credentials(client_id: str, client_secret: str, store: SecretStore | None = None) -> None:
    store = store or SecretStore()
    store.set("client_id", client_id.strip())
    store.set("client_secret", client_secret.strip())
