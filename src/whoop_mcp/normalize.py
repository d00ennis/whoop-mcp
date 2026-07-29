"""Rohantworten der WHOOP API in flache, lesbare Datensaetze uebersetzen.

Einheiten werden dabei in alltagstaugliche Groessen gebracht: Millisekunden zu
Stunden, Kilojoule zu Kilokalorien, Meter zu Kilometern. Die Rohwerte bleiben in
der Datenbank erhalten.
"""

from __future__ import annotations

KJ_PER_KCAL = 4.184


def _round(value, digits: int = 2):
    return round(value, digits) if isinstance(value, (int, float)) else None


def ms_to_hours(value) -> float | None:
    return _round(value / 3_600_000, 2) if isinstance(value, (int, float)) else None


def ms_to_minutes(value) -> float | None:
    return _round(value / 60_000, 1) if isinstance(value, (int, float)) else None


def kj_to_kcal(value) -> int | None:
    return round(value / KJ_PER_KCAL) if isinstance(value, (int, float)) else None


def day_of(record: dict, *keys: str) -> str | None:
    """Erster verfuegbarer Zeitstempel als reines Datum (YYYY-MM-DD)."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and len(value) >= 10:
            return value[:10]
    return None


def recovery(record: dict) -> dict:
    score = record.get("score") or {}
    return {
        "date": day_of(record, "created_at", "updated_at"),
        "cycle_id": record.get("cycle_id"),
        "sleep_id": record.get("sleep_id"),
        "scored": record.get("score_state") == "SCORED",
        "calibrating": score.get("user_calibrating"),
        "recovery_score": score.get("recovery_score"),
        "hrv_ms": _round(score.get("hrv_rmssd_milli"), 1),
        "resting_heart_rate": score.get("resting_heart_rate"),
        "spo2_percent": _round(score.get("spo2_percentage"), 1),
        "skin_temp_celsius": _round(score.get("skin_temp_celsius"), 1),
    }


def sleep(record: dict) -> dict:
    score = record.get("score") or {}
    stages = score.get("stage_summary") or {}
    needed = score.get("sleep_needed") or {}
    in_bed = stages.get("total_in_bed_time_milli")
    awake = stages.get("total_awake_time_milli")
    asleep = None
    if isinstance(in_bed, (int, float)) and isinstance(awake, (int, float)):
        asleep = in_bed - awake
    return {
        "date": day_of(record, "start", "created_at"),
        "sleep_id": record.get("id"),
        "cycle_id": record.get("cycle_id"),
        "nap": record.get("nap"),
        "scored": record.get("score_state") == "SCORED",
        "time_in_bed_hours": ms_to_hours(in_bed),
        "asleep_hours": ms_to_hours(asleep),
        "awake_hours": ms_to_hours(awake),
        "light_hours": ms_to_hours(stages.get("total_light_sleep_time_milli")),
        "deep_hours": ms_to_hours(stages.get("total_slow_wave_sleep_time_milli")),
        "rem_hours": ms_to_hours(stages.get("total_rem_sleep_time_milli")),
        "sleep_needed_hours": ms_to_hours(needed.get("baseline_milli")),
        "sleep_debt_hours": ms_to_hours(needed.get("need_from_sleep_debt_milli")),
        "sleep_cycles": stages.get("sleep_cycle_count"),
        "disturbances": stages.get("disturbance_count"),
        "performance_percent": _round(score.get("sleep_performance_percentage"), 1),
        "consistency_percent": _round(score.get("sleep_consistency_percentage"), 1),
        "efficiency_percent": _round(score.get("sleep_efficiency_percentage"), 1),
        "respiratory_rate": _round(score.get("respiratory_rate"), 1),
    }


def cycle(record: dict) -> dict:
    score = record.get("score") or {}
    return {
        "date": day_of(record, "start", "created_at"),
        "cycle_id": record.get("id"),
        "scored": record.get("score_state") == "SCORED",
        "strain": _round(score.get("strain"), 1),
        "calories_kcal": kj_to_kcal(score.get("kilojoule")),
        "average_heart_rate": score.get("average_heart_rate"),
        "max_heart_rate": score.get("max_heart_rate"),
        "start": record.get("start"),
        "end": record.get("end"),
    }


def _zone_minutes(zones: dict) -> dict:
    mapping = {
        "zone_zero_milli": "zone_0_minutes",
        "zone_one_milli": "zone_1_minutes",
        "zone_two_milli": "zone_2_minutes",
        "zone_three_milli": "zone_3_minutes",
        "zone_four_milli": "zone_4_minutes",
        "zone_five_milli": "zone_5_minutes",
    }
    return {out: ms_to_minutes(zones.get(src)) for src, out in mapping.items()}


def workout(record: dict) -> dict:
    score = record.get("score") or {}
    distance = score.get("distance_meter")
    result = {
        "date": day_of(record, "start", "created_at"),
        "workout_id": record.get("id"),
        "sport": record.get("sport_name"),
        "scored": record.get("score_state") == "SCORED",
        "strain": _round(score.get("strain"), 1),
        "average_heart_rate": score.get("average_heart_rate"),
        "max_heart_rate": score.get("max_heart_rate"),
        "calories_kcal": kj_to_kcal(score.get("kilojoule")),
        "distance_km": _round(distance / 1000, 2) if isinstance(distance, (int, float)) else None,
        "altitude_gain_meter": _round(score.get("altitude_gain_meter"), 1),
        "percent_recorded": _round(score.get("percent_recorded"), 1),
        "start": record.get("start"),
        "end": record.get("end"),
    }
    result.update(_zone_minutes(score.get("zone_durations") or {}))
    return result


def body(record: dict) -> dict:
    height = record.get("height_meter")
    return {
        "height_cm": _round(height * 100, 1) if isinstance(height, (int, float)) else None,
        "weight_kg": _round(record.get("weight_kilogram"), 1),
        "max_heart_rate": record.get("max_heart_rate"),
    }
