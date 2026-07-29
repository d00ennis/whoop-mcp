import json

from conftest import CYCLE, RECOVERY, SLEEP, WORKOUT
from whoop_mcp import sync
from whoop_mcp.store import Store


class FakeClient:
    def __init__(self):
        self.days_seen = []

    def _record(self, days):
        self.days_seen.append(days)

    def recoveries(self, days=7):
        self._record(days)
        return [RECOVERY]

    def sleeps(self, days=7):
        return [SLEEP]

    def cycles(self, days=7):
        return [CYCLE]

    def workouts(self, days=14):
        return [WORKOUT]

    def body_measurement(self):
        return {"height_meter": 1.8, "weight_kilogram": 80.0, "max_heart_rate": 195}


def test_run_writes_all_tables_and_export(tmp_path, monkeypatch):
    export = tmp_path / "whoop.json"
    monkeypatch.setenv("WHOOP_MCP_EXPORT_PATH", str(export))
    store = Store(tmp_path / "t.db")
    result = sync.run(client=FakeClient(), store=store, days=7)

    assert result["written"] == {"recovery": 1, "sleep": 1, "cycles": 1, "workouts": 1, "body": 1}
    payload = json.loads(export.read_text())
    assert payload["latest"]["recovery_score"] == 44
    assert payload["averages"]["last_7_days"]["strain"] == 5.3
    assert payload["workouts"][0]["sport"] == "running"


def test_first_run_uses_full_backfill(tmp_path):
    store = Store(tmp_path / "t.db")
    client = FakeClient()
    sync.run(client=client, store=store, write_export=False)
    assert client.days_seen[0] == sync.DEFAULT_BACKFILL_DAYS


def test_second_run_only_fetches_recent_days(tmp_path):
    store = Store(tmp_path / "t.db")
    sync.run(client=FakeClient(), store=store, write_export=False)
    client = FakeClient()
    sync.run(client=client, store=store, write_export=False)
    # Minimum zwei Tage Ueberlappung fuer nachtraeglich bewertete Aktivitaeten
    assert client.days_seen[0] == 2


def test_sync_is_idempotent(tmp_path):
    store = Store(tmp_path / "t.db")
    sync.run(client=FakeClient(), store=store, days=7, write_export=False)
    sync.run(client=FakeClient(), store=store, days=7, write_export=False)
    assert store.counts() == {"recovery": 1, "sleep": 1, "cycles": 1, "workouts": 1}
