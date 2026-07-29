from conftest import CYCLE, RECOVERY, SLEEP
from whoop_mcp import aggregate, normalize


def test_daily_merges_sources_by_date():
    rows = aggregate.daily(
        [normalize.recovery(RECOVERY)], [normalize.sleep(SLEEP)], [normalize.cycle(CYCLE)]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["date"] == "2026-07-28"
    assert row["recovery_score"] == 44
    assert row["strain"] == 5.3
    assert row["asleep_hours"] == 8.02


def test_daily_ignores_naps():
    nap = dict(SLEEP, id="nap-1", nap=True)
    rows = aggregate.daily([], [normalize.sleep(nap)], [])
    assert rows == [] or rows[0].get("asleep_hours") is None


def test_daily_sorted_descending():
    older = dict(CYCLE, id=1, start="2026-07-20T02:00:00.000Z")
    rows = aggregate.daily([], [], [normalize.cycle(CYCLE), normalize.cycle(older)])
    assert [r["date"] for r in rows] == ["2026-07-28", "2026-07-20"]


def test_averages_skip_missing_values():
    rows = [{"recovery_score": 40}, {"recovery_score": 60}, {"recovery_score": None}]
    assert aggregate.averages(rows, ("recovery_score",)) == {"recovery_score": 50.0}


def test_averages_of_empty_input_is_none():
    assert aggregate.averages([], ("hrv_ms",)) == {"hrv_ms": None}


def test_trend_compares_recent_against_baseline():
    rows = [{"hrv_ms": 60}] * 7 + [{"hrv_ms": 40}] * 21
    result = aggregate.trend(rows, "hrv_ms", recent=7, baseline=28)
    assert result["recent_average"] == 60.0
    assert result["delta"] > 0
    assert result["sample_size"] == 28


def test_evening_cycle_and_its_sleep_land_on_the_same_day():
    # Nacht vom 27. auf den 28. Juli, Ortszeit Berlin
    cycle = dict(CYCLE, id=555, start="2026-07-27T21:32:51.930Z", timezone_offset="+02:00")
    night = dict(
        SLEEP,
        id="night-1",
        cycle_id=555,
        start="2026-07-27T21:32:51.930Z",
        end="2026-07-28T05:59:51.390Z",
        timezone_offset="+02:00",
    )
    recovery = dict(RECOVERY, cycle_id=555)
    rows = aggregate.daily(
        [normalize.recovery(recovery)], [normalize.sleep(night)], [normalize.cycle(cycle)]
    )
    assert len(rows) == 1
    assert rows[0]["date"] == "2026-07-28"
    assert rows[0]["recovery_score"] == 44
    assert rows[0]["sleep_window"] == "23:32–07:59"
