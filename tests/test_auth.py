import json
import time

import httpx
import pytest
from whoop_mcp import auth
from whoop_mcp.config import ClientCredentials, SecretStore

CREDS = ClientCredentials(client_id="id", client_secret="secret")


def store_for(tmp_path):
    return SecretStore(fallback=tmp_path / "secrets.json")


def test_authorize_url_requests_offline_scope():
    url = auth.build_authorize_url("id", "http://localhost:8765/callback", "abcdefgh")
    assert "offline" in url
    assert "response_type=code" in url
    assert "state=abcdefgh" in url


def test_tokenset_expiry_uses_margin():
    fresh = auth.TokenSet("a", "r", time.time() + 3600)
    stale = auth.TokenSet("a", "r", time.time() + 10)
    assert not fresh.is_expired()
    assert stale.is_expired()


def test_tokenset_requires_access_token():
    with pytest.raises(auth.AuthError):
        auth.TokenSet.from_response({"error": "invalid_grant"})


def test_exchange_code_posts_form_encoded():
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode()
        captured["content_type"] = request.headers["Content-Type"]
        return httpx.Response(200, json={"access_token": "a", "refresh_token": "r", "expires_in": 3600})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tokens = auth.exchange_code(CREDS, "code123", "http://localhost:8765/callback", client=client)
    assert tokens.access_token == "a"
    assert "grant_type=authorization_code" in captured["body"]
    assert captured["content_type"].startswith("application/x-www-form-urlencoded")


def test_refresh_includes_offline_scope():
    captured = {}

    def handler(request):
        captured["body"] = request.content.decode()
        return httpx.Response(200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 3600})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    auth.refresh_tokens(CREDS, "r1", client=client)
    assert "scope=offline" in captured["body"]
    assert "grant_type=refresh_token" in captured["body"]


def test_refresh_error_is_wrapped():
    def handler(request):
        return httpx.Response(400, text="invalid_grant")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(auth.AuthError):
        auth.refresh_tokens(CREDS, "stale", client=client)


def test_manager_persists_rotated_refresh_token(tmp_path, monkeypatch):
    store = store_for(tmp_path)
    manager = auth.TokenManager(creds=CREDS, store=store)
    manager.save(auth.TokenSet("old-access", "old-refresh", time.time() - 1))

    monkeypatch.setattr(
        auth, "refresh_tokens",
        lambda creds, token, client=None: auth.TokenSet("new-access", "new-refresh", time.time() + 3600),
    )
    assert manager.access_token() == "new-access"

    reloaded = json.loads(store.get(auth.TOKEN_KEY))
    assert reloaded["refresh_token"] == "new-refresh"


def test_manager_keeps_old_refresh_token_if_response_omits_it(tmp_path, monkeypatch):
    store = store_for(tmp_path)
    manager = auth.TokenManager(creds=CREDS, store=store)
    manager.save(auth.TokenSet("old", "keep-me", time.time() - 1))
    monkeypatch.setattr(
        auth, "refresh_tokens",
        lambda creds, token, client=None: auth.TokenSet("new", None, time.time() + 3600),
    )
    manager.access_token()
    assert json.loads(store.get(auth.TOKEN_KEY))["refresh_token"] == "keep-me"


def test_manager_without_tokens_raises(tmp_path):
    manager = auth.TokenManager(creds=CREDS, store=store_for(tmp_path))
    with pytest.raises(auth.AuthError):
        manager.access_token()


def test_secret_store_file_fallback_is_owner_only(tmp_path):
    store = store_for(tmp_path)
    store.set("client_id", "abc")
    assert store.get("client_id") == "abc"
    assert oct((tmp_path / "secrets.json").stat().st_mode)[-3:] == "600"
