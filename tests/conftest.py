import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Tests fassen weder Keychain noch das echte Datenverzeichnis an."""
    monkeypatch.setenv("WHOOP_MCP_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("WHOOP_MCP_EXPORT_PATH", str(tmp_path / "data" / "whoop.json"))
    monkeypatch.setenv("WHOOP_MCP_NO_KEYRING", "1")
    yield


RECOVERY = {
    "cycle_id": 93845,
    "sleep_id": "123e4567-e89b-12d3-a456-426614174000",
    "created_at": "2026-07-28T11:25:44.774Z",
    "score_state": "SCORED",
    "score": {
        "user_calibrating": False,
        "recovery_score": 44,
        "resting_heart_rate": 64,
        "hrv_rmssd_milli": 31.813562,
        "spo2_percentage": 95.6875,
        "skin_temp_celsius": 33.7,
    },
}

SLEEP = {
    "id": "ecfc6a15-4661-442f-a9a4-f160dd7afae8",
    "cycle_id": 93845,
    "start": "2026-07-28T02:25:44.774Z",
    "end": "2026-07-28T10:25:44.774Z",
    "nap": False,
    "score_state": "SCORED",
    "score": {
        "stage_summary": {
            "total_in_bed_time_milli": 30272735,
            "total_awake_time_milli": 1403507,
            "total_light_sleep_time_milli": 14905851,
            "total_slow_wave_sleep_time_milli": 6630370,
            "total_rem_sleep_time_milli": 5879573,
            "sleep_cycle_count": 3,
            "disturbance_count": 12,
        },
        "sleep_needed": {"baseline_milli": 27395716, "need_from_sleep_debt_milli": 352230},
        "respiratory_rate": 16.11328125,
        "sleep_performance_percentage": 98,
        "sleep_consistency_percentage": 90,
        "sleep_efficiency_percentage": 91.69533848,
    },
}

CYCLE = {
    "id": 93845,
    "start": "2026-07-28T02:25:44.774Z",
    "end": "2026-07-28T10:25:44.774Z",
    "score_state": "SCORED",
    "score": {
        "strain": 5.2951527,
        "kilojoule": 8288.297,
        "average_heart_rate": 68,
        "max_heart_rate": 141,
    },
}

WORKOUT = {
    "id": "aaaaaaaa-4661-442f-a9a4-f160dd7afae8",
    "start": "2026-07-28T06:00:00.000Z",
    "end": "2026-07-28T07:00:00.000Z",
    "sport_name": "running",
    "score_state": "SCORED",
    "score": {
        "strain": 8.2463,
        "average_heart_rate": 123,
        "max_heart_rate": 146,
        "kilojoule": 1569.34,
        "percent_recorded": 100,
        "distance_meter": 5000.0,
        "altitude_gain_meter": 46.64,
        "zone_durations": {
            "zone_zero_milli": 300000,
            "zone_one_milli": 600000,
            "zone_two_milli": 900000,
            "zone_three_milli": 900000,
            "zone_four_milli": 600000,
            "zone_five_milli": 300000,
        },
    },
}
