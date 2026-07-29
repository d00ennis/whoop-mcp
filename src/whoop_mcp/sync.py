"""Taeglicher Abgleich: WHOOP abrufen, lokal speichern, Export schreiben."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from . import aggregate, normalize
from .client import WhoopClient
from .config import export_path
from .store import Store

LAST_SYNC_KEY = "last_sync"
DEFAULT_BACKFILL_DAYS = 90
EXPORT_DAYS = 180


def _days_since_last_sync(store: Store, default: int) -> int:
    marker = store.get_meta(LAST_SYNC_KEY)
    if not marker:
        return default
    try:
        last = datetime.fromisoformat(marker)
    except ValueError:
        return default
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    delta = (datetime.now(timezone.utc) - last).days
    # Ein Tag Ueberlappung faengt nachtraeglich bewertete Aktivitaeten ab.
    return max(2, min(delta + 1, default))


def run(
    client: WhoopClient | None = None,
    store: Store | None = None,
    days: int | None = None,
    write_export: bool = True,
) -> dict:
    client = client or WhoopClient()
    store = store or Store()
    days = days or _days_since_last_sync(store, DEFAULT_BACKFILL_DAYS)

    written = {
        "recovery": store.upsert("recovery", client.recoveries(days=days)),
        "sleep": store.upsert("sleep", client.sleeps(days=days)),
        "cycles": store.upsert("cycles", client.cycles(days=days)),
        "workouts": store.upsert("workouts", client.workouts(days=days)),
    }

    try:
        store.save_body(client.body_measurement())
        written["body"] = 1
    except Exception:
        written["body"] = 0

    store.set_meta(LAST_SYNC_KEY, datetime.now(timezone.utc).isoformat())

    result = {"days": days, "written": written, "totals": store.counts()}
    if write_export:
        result["export"] = str(build_export(store))
    return result


def build_export(store: Store, days: int = EXPORT_DAYS):
    """Flaches JSON fuer das Life-OS-Dashboard schreiben."""
    recoveries = [
        normalize.recovery(json.loads(row["raw"])) for row in store.recent("recovery", days)
    ]
    sleeps = [normalize.sleep(json.loads(row["raw"])) for row in store.recent("sleep", days)]
    cycles = [normalize.cycle(json.loads(row["raw"])) for row in store.recent("cycles", days)]
    workouts = [
        normalize.workout(json.loads(row["raw"])) for row in store.recent("workouts", days)
    ]

    rows = aggregate.daily(recoveries, sleeps, cycles)
    body_rows = store.query("SELECT * FROM body ORDER BY measured_on DESC LIMIT 1")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "whoop-mcp",
        "latest": rows[0] if rows else None,
        "days": rows,
        "workouts": workouts,
        "body": body_rows[0] if body_rows else None,
        "averages": {
            "last_7_days": aggregate.averages(rows[:7]),
            "last_30_days": aggregate.averages(rows[:30]),
        },
        "trends": [
            t
            for t in (
                aggregate.trend(rows, "recovery_score"),
                aggregate.trend(rows, "hrv_ms"),
                aggregate.trend(rows, "resting_heart_rate"),
                aggregate.trend(rows, "asleep_hours"),
                aggregate.trend(rows, "strain"),
            )
            if t
        ],
    }

    path = export_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return path
