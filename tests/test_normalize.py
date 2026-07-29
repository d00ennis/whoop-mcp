from conftest import CYCLE, RECOVERY, SLEEP, WORKOUT
from whoop_mcp import normalize


def test_recovery_flattens_score():
    result = normalize.recovery(RECOVERY)
    assert result["date"] == "2026-07-28"
    assert result["recovery_score"] == 44
    assert result["hrv_ms"] == 31.8
    assert result["resting_heart_rate"] == 64
    assert result["scored"] is True


def test_sleep_converts_milliseconds_to_hours():
    result = normalize.sleep(SLEEP)
    assert result["time_in_bed_hours"] == 8.41
    # in bed minus awake
    assert result["asleep_hours"] == 8.02
    assert result["deep_hours"] == 1.84
    assert result["performance_percent"] == 98
    assert result["disturbances"] == 12


def test_cycle_converts_kilojoule_to_kcal():
    result = normalize.cycle(CYCLE)
    assert result["strain"] == 5.3
    assert result["calories_kcal"] == 1981
    assert result["cycle_id"] == 93845


def test_workout_converts_distance_and_zones():
    result = normalize.workout(WORKOUT)
    assert result["distance_km"] == 5.0
    assert result["sport"] == "running"
    assert result["zone_three_minutes" if False else "zone_3_minutes"] == 15.0
    assert result["zone_0_minutes"] == 5.0


def test_body_converts_height_to_centimetres():
    result = normalize.body({"height_meter": 1.8288, "weight_kilogram": 90.7185, "max_heart_rate": 200})
    assert result["height_cm"] == 182.9
    assert result["weight_kg"] == 90.7


def test_missing_score_does_not_raise():
    result = normalize.recovery({"cycle_id": 1, "score_state": "PENDING_SCORE"})
    assert result["recovery_score"] is None
    assert result["scored"] is False
