"""OAuth-2.0-Flow und Token-Verwaltung fuer die WHOOP API.

WHOOP-Besonderheiten, die hier beruecksichtigt werden:

* Ein Refresh Token wird nur ausgegeben, wenn der Scope ``offline`` angefragt
  wurde.
* Refresh Tokens rotieren: nach jeder Erneuerung ist der alte Token ungueltig
  und der neue muss sofort persistiert werden.
* Der ``state``-Parameter muss mindestens acht Zeichen lang sein.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

from .config import (
    AUTH_URL,
    SCOPES,
    TOKEN_URL,
    ClientCredentials,
    SecretStore,
    load_credentials,
    redirect_uri as default_redirect_uri,
)

TOKEN_KEY = "tokens"
REFRESH_MARGIN_SECONDS = 120


class AuthError(RuntimeError):
    """Fehler waehrend Authorisierung oder Token-Erneuerung."""


@dataclass
class TokenSet:
    access_token: str
    refresh_token: str | None
    expires_at: float
    scope: str = ""

    @classmethod
    def from_response(cls, payload: dict) -> "TokenSet":
        try:
            access_token = payload["access_token"]
        except KeyError as exc:
            raise AuthError(f"Token-Antwort ohne access_token: {payload}") from exc
        expires_in = float(payload.get("expires_in", 3600))
        return cls(
            access_token=access_token,
            refresh_token=payload.get("refresh_token"),
            expires_at=time.time() + expires_in,
            scope=payload.get("scope", ""),
        )

    def is_expired(self, margin: float = REFRESH_MARGIN_SECONDS) -> bool:
        return time.time() + margin >= self.expires_at


def build_authorize_url(
    client_id: str, redirect_uri: str, state: str, scopes: list[str] | None = None
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes or SCOPES),
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def _post_token(payload: dict, client: httpx.Client | None = None) -> TokenSet:
    owned = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.post(
            TOKEN_URL,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    finally:
        if owned:
            client.close()
    if response.status_code >= 400:
        raise AuthError(f"Token-Endpunkt antwortete {response.status_code}: {response.text}")
    return TokenSet.from_response(response.json())


def exchange_code(
    creds: ClientCredentials, code: str, redirect_uri: str, client: httpx.Client | None = None
) -> TokenSet:
    return _post_token(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        },
        client=client,
    )


def refresh_tokens(
    creds: ClientCredentials, refresh_token: str, client: httpx.Client | None = None
) -> TokenSet:
    return _post_token(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scope": "offline",
        },
        client=client,
    )


class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):  # noqa: N802 - von BaseHTTPRequestHandler vorgegeben
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip("/") not in ("/callback", ""):
            self.send_response(404)
            self.end_headers()
            return
        query = urllib.parse.parse_qs(parsed.query)
        type(self).result = {k: v[0] for k, v in query.items()}
        body = (
            "<html><body style='font-family:-apple-system;padding:3rem'>"
            "<h2>WHOOP verbunden</h2>"
            "<p>Du kannst dieses Fenster schliessen.</p></body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # Konsole sauber halten
        return


def wait_for_callback(port: int, timeout: float = 300) -> dict:
    """Nimmt genau eine Weiterleitung von WHOOP entgegen und liefert deren Query."""
    _CallbackHandler.result = {}
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 1
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.2})
    thread.daemon = True
    thread.start()
    deadline = time.time() + timeout
    try:
        while time.time() < deadline:
            if _CallbackHandler.result:
                return dict(_CallbackHandler.result)
            time.sleep(0.2)
    finally:
        server.shutdown()
        server.server_close()
    raise AuthError("Zeitueberschreitung: keine Antwort von WHOOP erhalten.")


class TokenManager:
    """Haelt den Token-Satz aktuell und persistiert Rotationen sofort."""

    def __init__(self, creds: ClientCredentials | None = None, store: SecretStore | None = None):
        self.store = store or SecretStore()
        self.creds = creds or load_credentials(self.store)
        self._lock = threading.Lock()
        self._tokens = self._load()

    def _load(self) -> TokenSet | None:
        raw = self.store.get(TOKEN_KEY)
        if not raw:
            return None
        try:
            return TokenSet(**json.loads(raw))
        except (ValueError, TypeError):
            return None

    def save(self, tokens: TokenSet) -> None:
        self._tokens = tokens
        self.store.set(TOKEN_KEY, json.dumps(asdict(tokens)))

    @property
    def is_authorized(self) -> bool:
        return self._tokens is not None

    def access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            tokens = self._tokens
            if tokens is None:
                raise AuthError(
                    "Noch nicht mit WHOOP verbunden. Bitte 'whoop-mcp auth' ausfuehren."
                )
            if force_refresh or tokens.is_expired():
                if not tokens.refresh_token:
                    raise AuthError(
                        "Kein Refresh Token vorhanden. Bitte 'whoop-mcp auth' erneut ausfuehren."
                    )
                refreshed = refresh_tokens(self.creds, tokens.refresh_token)
                # WHOOP rotiert den Refresh Token; faellt er in der Antwort weg,
                # bleibt der bisherige gueltig.
                if not refreshed.refresh_token:
                    refreshed.refresh_token = tokens.refresh_token
                self.save(refreshed)
                return refreshed.access_token
            return tokens.access_token

    def clear(self) -> None:
        with self._lock:
            self._tokens = None
            self.store.delete(TOKEN_KEY)


def authorize(
    creds: ClientCredentials | None = None,
    store: SecretStore | None = None,
    open_browser: bool = True,
) -> TokenSet:
    """Vollstaendiger interaktiver Authorization-Code-Flow."""
    store = store or SecretStore()
    creds = creds or load_credentials(store)
    uri = default_redirect_uri()
    parsed = urllib.parse.urlparse(uri)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    state = secrets.token_urlsafe(16)

    url = build_authorize_url(creds.client_id, uri, state)
    print("Oeffne diese URL im Browser, falls sie sich nicht automatisch oeffnet:\n")
    print(url + "\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    query = wait_for_callback(port)
    if "error" in query:
        raise AuthError(f"WHOOP meldete einen Fehler: {query.get('error_description', query['error'])}")
    if query.get("state") != state:
        raise AuthError("State stimmt nicht ueberein - Abbruch aus Sicherheitsgruenden.")
    code = query.get("code")
    if not code:
        raise AuthError(f"Kein Authorization Code in der Weiterleitung: {query}")

    tokens = exchange_code(creds, code, uri)
    if not tokens.refresh_token:
        raise AuthError(
            "WHOOP hat keinen Refresh Token geliefert. Ist der Scope 'offline' in der App aktiviert?"
        )
    manager = TokenManager(creds=creds, store=store)
    manager.save(tokens)
    return tokens
