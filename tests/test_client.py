import httpx
import pytest
from conftest import CYCLE, RECOVERY
from whoop_mcp.client import WhoopAPIError, WhoopClient, window


class FakeTokens:
    def __init__(self):
        self.calls = []

    def access_token(self, force_refresh=False):
        self.calls.append(force_refresh)
        return "refreshed" if force_refresh else "initial"


def client_with(handler):
    transport = httpx.MockTransport(handler)
    return WhoopClient(tokens=FakeTokens(), http=httpx.Client(transport=transport))


def test_window_returns_iso_range():
    start, end = window(7)
    assert start.endswith("Z") and end.endswith("Z")
    assert start < end


def test_collection_follows_pagination():
    pages = [
        {"records": [RECOVERY], "next_token": "abc"},
        {"records": [dict(RECOVERY, cycle_id=2)], "next_token": None},
    ]
    seen = []

    def handler(request):
        seen.append(request.url.params.get("nextToken"))
        return httpx.Response(200, json=pages[len(seen) - 1])

    client = client_with(handler)
    records = client.recoveries(days=7)
    assert len(records) == 2
    assert seen == [None, "abc"]


def test_limit_caps_number_of_records():
    def handler(request):
        assert int(request.url.params["limit"]) == 3
        return httpx.Response(200, json={"records": [RECOVERY] * 3, "next_token": None})

    assert len(client_with(handler).recoveries(days=7, limit=3)) == 3


def test_401_triggers_single_token_refresh():
    responses = [
        httpx.Response(401, json={"error": "expired"}),
        httpx.Response(200, json={"records": [CYCLE], "next_token": None}),
    ]
    order = []

    def handler(request):
        order.append(request.headers["Authorization"])
        return responses[len(order) - 1]

    client = client_with(handler)
    assert len(client.cycles(days=1)) == 1
    assert order == ["Bearer initial", "Bearer refreshed"]


def test_persistent_401_raises():
    def handler(request):
        return httpx.Response(401, json={"error": "nope"})

    with pytest.raises(WhoopAPIError) as exc:
        client_with(handler).cycles(days=1)
    assert exc.value.status_code == 401


def test_429_is_retried(monkeypatch):
    monkeypatch.setattr("whoop_mcp.client.time.sleep", lambda *_: None)
    responses = [
        httpx.Response(429, headers={"Retry-After": "1"}),
        httpx.Response(200, json={"records": [], "next_token": None}),
    ]
    calls = []

    def handler(request):
        calls.append(1)
        return responses[len(calls) - 1]

    assert client_with(handler).sleeps(days=1) == []
    assert len(calls) == 2


def test_400_raises_immediately():
    def handler(request):
        return httpx.Response(400, text="bad range")

    with pytest.raises(WhoopAPIError):
        client_with(handler).workouts(days=1)


def test_body_measurement_uses_single_resource():
    def handler(request):
        assert request.url.path.endswith("/v2/user/measurement/body")
        return httpx.Response(200, json={"height_meter": 1.8, "weight_kilogram": 80.0})

    assert client_with(handler).body_measurement()["weight_kilogram"] == 80.0
