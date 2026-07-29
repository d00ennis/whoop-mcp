"""Zusammenfuehren und Verdichten normalisierter Datensaetze."""

from __future__ import annotations

from statistics import mean

DAILY_AVERAGE_KEYS = (
    "recovery_score",
    "hrv_ms",
    "resting_heart_rate",
    "asleep_hours",
    "sleep_performance_percent",
    "strain",
    "calories_kcal",
)


def daily(recoveries: list[dict], sleeps: list[dict], cycles: list[dict]) -> list[dict]:
    """Ein Datensatz pro Tag aus Recovery, Schlaf und Cycle.

    Naps werden ausgelassen, damit pro Tag der Hauptschlaf gewertet wird.
    """
    days: dict[str, dict] = {}

    for record in cycles:
        day = record.get("date")
        if not day:
            continue
        days.setdefault(day, {"date": day}).update(
            {
                "strain": record.get("strain"),
                "calories_kcal": record.get("calories_kcal"),
                "average_heart_rate": record.get("average_heart_rate"),
                "max_heart_rate": record.get("max_heart_rate"),
            }
        )

    by_cycle = {r.get("cycle_id"): r for r in recoveries if r.get("cycle_id") is not None}
    for record in cycles:
        day = record.get("date")
        recovery = by_cycle.get(record.get("cycle_id"))
        if not day or not recovery:
            continue
        days.setdefault(day, {"date": day}).update(
            {
                "recovery_score": recovery.get("recovery_score"),
                "hrv_ms": recovery.get("hrv_ms"),
                "resting_heart_rate": recovery.get("resting_heart_rate"),
                "spo2_percent": recovery.get("spo2_percent"),
                "skin_temp_celsius": recovery.get("skin_temp_celsius"),
            }
        )

    for record in sleeps:
        day = record.get("date")
        if not day or record.get("nap"):
            continue
        entry = days.setdefault(day, {"date": day})
        # Bei mehreren Schlafphasen pro Tag gewinnt die laengste.
        existing = entry.get("asleep_hours")
        incoming = record.get("asleep_hours")
        if existing is not None and incoming is not None and existing >= incoming:
            continue
        entry.update(
            {
                "asleep_hours": record.get("asleep_hours"),
                "sleep_performance_percent": record.get("performance_percent"),
                "sleep_consistency_percent": record.get("consistency_percent"),
                "sleep_efficiency_percent": record.get("efficiency_percent"),
                "deep_hours": record.get("deep_hours"),
                "rem_hours": record.get("rem_hours"),
                "respiratory_rate": record.get("respiratory_rate"),
                "disturbances": record.get("disturbances"),
            }
        )

    return sorted(days.values(), key=lambda row: row["date"], reverse=True)


def averages(rows: list[dict], keys: tuple[str, ...] = DAILY_AVERAGE_KEYS) -> dict:
    """Mittelwerte ueber vorhandene Werte; fehlende Werte werden ignoriert."""
    result = {}
    for key in keys:
        values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
        result[key] = round(mean(values), 1) if values else None
    return result


def trend(rows: list[dict], key: str, recent: int = 7, baseline: int = 28) -> dict | None:
    """Kurzfristiger Schnitt gegen laengeren Schnitt fuer eine Kennzahl."""
    values = [row[key] for row in rows if isinstance(row.get(key), (int, float))]
    if len(values) < 2:
        return None
    short = values[:recent]
    long = values[:baseline]
    if not short or not long:
        return None
    short_avg = round(mean(short), 1)
    long_avg = round(mean(long), 1)
    return {
        "metric": key,
        "recent_average": short_avg,
        "baseline_average": long_avg,
        "delta": round(short_avg - long_avg, 1),
        "sample_size": len(long),
    }
