from conftest import CYCLE, RECOVERY, SLEEP, WORKOUT
from whoop_mcp.store import Store


def test_upsert_is_idempotent(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.upsert("recovery", [RECOVERY]) == 1
    store.upsert("recovery", [RECOVERY])
    assert store.counts()["recovery"] == 1


def test_upsert_updates_changed_values(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert("recovery", [RECOVERY])
    updated = dict(RECOVERY, score=dict(RECOVERY["score"], recovery_score=91))
    store.upsert("recovery", [updated])
    rows = store.query("SELECT recovery_score FROM recovery")
    assert len(rows) == 1 and rows[0]["recovery_score"] == 91


def test_records_without_primary_key_are_skipped(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.upsert("recovery", [{"score": {}}]) == 0


def test_all_tables_accept_their_records(tmp_path):
    store = Store(tmp_path / "t.db")
    store.upsert("sleep", [SLEEP])
    store.upsert("cycles", [CYCLE])
    store.upsert("workouts", [WORKOUT])
    counts = store.counts()
    assert counts["sleep"] == 1 and counts["cycles"] == 1 and counts["workouts"] == 1


def test_raw_payload_is_preserved(tmp_path):
    import json

    store = Store(tmp_path / "t.db")
    store.upsert("workouts", [WORKOUT])
    raw = json.loads(store.query("SELECT raw FROM workouts")[0]["raw"])
    assert raw["score"]["zone_durations"]["zone_five_milli"] == 300000


def test_meta_roundtrip(tmp_path):
    store = Store(tmp_path / "t.db")
    assert store.get_meta("last_sync") is None
    store.set_meta("last_sync", "2026-07-29T06:00:00+00:00")
    store.set_meta("last_sync", "2026-07-29T07:00:00+00:00")
    assert store.get_meta("last_sync") == "2026-07-29T07:00:00+00:00"


def test_unknown_table_rejected(tmp_path):
    import pytest

    store = Store(tmp_path / "t.db")
    with pytest.raises(ValueError):
        store.upsert("robert'; DROP TABLE sleep; --", [])
    with pytest.raises(ValueError):
        store.recent("robert'; DROP TABLE sleep; --")
