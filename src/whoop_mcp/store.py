"""Lokale SQLite-Historie.

Jede Tabelle haelt den normalisierten Datensatz als Spalten plus die Rohantwort
als JSON. Schreibvorgaenge sind idempotent: derselbe WHOOP-Datensatz kann
beliebig oft synchronisiert werden, ohne Duplikate zu erzeugen.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import normalize
from .config import db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS recovery (
    cycle_id INTEGER PRIMARY KEY,
    date TEXT,
    recovery_score REAL,
    hrv_ms REAL,
    resting_heart_rate REAL,
    spo2_percent REAL,
    skin_temp_celsius REAL,
    raw TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sleep (
    sleep_id TEXT PRIMARY KEY,
    date TEXT,
    nap INTEGER,
    asleep_hours REAL,
    time_in_bed_hours REAL,
    light_hours REAL,
    deep_hours REAL,
    rem_hours REAL,
    performance_percent REAL,
    consistency_percent REAL,
    efficiency_percent REAL,
    respiratory_rate REAL,
    disturbances INTEGER,
    raw TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cycles (
    cycle_id INTEGER PRIMARY KEY,
    date TEXT,
    strain REAL,
    calories_kcal INTEGER,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    raw TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workouts (
    workout_id TEXT PRIMARY KEY,
    date TEXT,
    sport TEXT,
    strain REAL,
    average_heart_rate INTEGER,
    max_heart_rate INTEGER,
    calories_kcal INTEGER,
    distance_km REAL,
    raw TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS body (
    measured_on TEXT PRIMARY KEY,
    height_cm REAL,
    weight_kg REAL,
    max_heart_rate INTEGER
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE INDEX IF NOT EXISTS idx_recovery_date ON recovery(date);
CREATE INDEX IF NOT EXISTS idx_sleep_date ON sleep(date);
CREATE INDEX IF NOT EXISTS idx_cycles_date ON cycles(date);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);
"""

_UPSERTS = {
    "recovery": (
        "INSERT INTO recovery (cycle_id, date, recovery_score, hrv_ms, resting_heart_rate,"
        " spo2_percent, skin_temp_celsius, raw) VALUES (?,?,?,?,?,?,?,?)"
        " ON CONFLICT(cycle_id) DO UPDATE SET date=excluded.date,"
        " recovery_score=excluded.recovery_score, hrv_ms=excluded.hrv_ms,"
        " resting_heart_rate=excluded.resting_heart_rate, spo2_percent=excluded.spo2_percent,"
        " skin_temp_celsius=excluded.skin_temp_celsius, raw=excluded.raw",
        ("cycle_id", "date", "recovery_score", "hrv_ms", "resting_heart_rate",
         "spo2_percent", "skin_temp_celsius"),
    ),
    "sleep": (
        "INSERT INTO sleep (sleep_id, date, nap, asleep_hours, time_in_bed_hours, light_hours,"
        " deep_hours, rem_hours, performance_percent, consistency_percent, efficiency_percent,"
        " respiratory_rate, disturbances, raw) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(sleep_id) DO UPDATE SET date=excluded.date, nap=excluded.nap,"
        " asleep_hours=excluded.asleep_hours, time_in_bed_hours=excluded.time_in_bed_hours,"
        " light_hours=excluded.light_hours, deep_hours=excluded.deep_hours,"
        " rem_hours=excluded.rem_hours, performance_percent=excluded.performance_percent,"
        " consistency_percent=excluded.consistency_percent,"
        " efficiency_percent=excluded.efficiency_percent,"
        " respiratory_rate=excluded.respiratory_rate, disturbances=excluded.disturbances,"
        " raw=excluded.raw",
        ("sleep_id", "date", "nap", "asleep_hours", "time_in_bed_hours", "light_hours",
         "deep_hours", "rem_hours", "performance_percent", "consistency_percent",
         "efficiency_percent", "respiratory_rate", "disturbances"),
    ),
    "cycles": (
        "INSERT INTO cycles (cycle_id, date, strain, calories_kcal, average_heart_rate,"
        " max_heart_rate, raw) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(cycle_id) DO UPDATE SET date=excluded.date, strain=excluded.strain,"
        " calories_kcal=excluded.calories_kcal,"
        " average_heart_rate=excluded.average_heart_rate,"
        " max_heart_rate=excluded.max_heart_rate, raw=excluded.raw",
        ("cycle_id", "date", "strain", "calories_kcal", "average_heart_rate", "max_heart_rate"),
    ),
    "workouts": (
        "INSERT INTO workouts (workout_id, date, sport, strain, average_heart_rate,"
        " max_heart_rate, calories_kcal, distance_km, raw) VALUES (?,?,?,?,?,?,?,?,?)"
        " ON CONFLICT(workout_id) DO UPDATE SET date=excluded.date, sport=excluded.sport,"
        " strain=excluded.strain, average_heart_rate=excluded.average_heart_rate,"
        " max_heart_rate=excluded.max_heart_rate, calories_kcal=excluded.calories_kcal,"
        " distance_km=excluded.distance_km, raw=excluded.raw",
        ("workout_id", "date", "sport", "strain", "average_heart_rate", "max_heart_rate",
         "calories_kcal", "distance_km"),
    ),
}

_NORMALIZERS = {
    "recovery": normalize.recovery,
    "sleep": normalize.sleep,
    "cycles": normalize.cycle,
    "workouts": normalize.workout,
}


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def upsert(self, table: str, records: list[dict]) -> int:
        """Rohdatensaetze normalisieren und idempotent schreiben."""
        if table not in _UPSERTS:
            raise ValueError(f"Unbekannte Tabelle: {table}")
        sql, fields = _UPSERTS[table]
        normalizer = _NORMALIZERS[table]
        rows = []
        for raw in records:
            flat = normalizer(raw)
            key = flat.get(fields[0])
            if key is None:
                continue  # ohne Primaerschluessel nicht speicherbar
            rows.append(tuple(flat.get(f) for f in fields) + (json.dumps(raw),))
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(sql, rows)
        return len(rows)

    def save_body(self, measurement: dict, measured_on: str | None = None) -> None:
        flat = normalize.body(measurement)
        day = measured_on or datetime.now(timezone.utc).date().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO body (measured_on, height_cm, weight_kg, max_heart_rate)"
                " VALUES (?,?,?,?) ON CONFLICT(measured_on) DO UPDATE SET"
                " height_cm=excluded.height_cm, weight_kg=excluded.weight_kg,"
                " max_heart_rate=excluded.max_heart_rate",
                (day, flat["height_cm"], flat["weight_kg"], flat["max_heart_rate"]),
            )

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def recent(self, table: str, days: int = 30, columns: str = "*") -> list[dict]:
        if table not in _UPSERTS:
            raise ValueError(f"Unbekannte Tabelle: {table}")
        return self.query(
            f"SELECT {columns} FROM {table} WHERE date >= date('now', ?)"
            " ORDER BY date DESC",
            (f"-{int(days)} days",),
        )

    def counts(self) -> dict[str, int]:
        return {
            table: self.query(f"SELECT COUNT(*) AS n FROM {table}")[0]["n"]
            for table in ("recovery", "sleep", "cycles", "workouts")
        }

    def get_meta(self, key: str) -> str | None:
        rows = self.query("SELECT value FROM meta WHERE key = ?", (key,))
        return rows[0]["value"] if rows else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?,?)"
                " ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
