import pytest
from whoop_mcp import lifeos

DASHBOARD = '''<html><script>
const ATH = {  updated:"20.07.2026", phase:"Phase 1",
  proteinTarget:203, kfaBand:[10,11],
  today:{ recovery:11, sleepPct:50, sleepH:6.00, sleepWin:"01:00-06:00", strain:9.9,
          weight:81.50, kfa:13.5, plan:"Lockerer Z2-Lauf, ruhig {kein JSON}" },
  recovery:[
    ["20.06.",11],["21.06.",63]
  ],
  weight:[["05.06.",81.05,13.4,0]],
  activities:[["27.07.","Kraft",3,49]]
};
</script></html>'''

PAYLOAD = {
    "days": [
        {"date": "2026-07-28", "recovery_score": 82, "sleep_performance_percent": 85,
         "asleep_hours": 8.29, "sleep_window": "23:32–07:59", "strain": 0.1},
        {"date": "2026-07-27", "recovery_score": 71, "strain": 12.9},
        {"date": "2026-07-26", "recovery_score": None, "strain": 5.0},
    ]
}


def test_select_data_uses_newest_scored_day():
    data = lifeos.select_data(PAYLOAD)
    assert data["updated"] == "2026-07-28"
    assert data["today"]["recovery"] == 82
    assert data["today"]["sleepWin"] == "23:32–07:59"


def test_select_data_series_is_chronological_and_skips_unscored():
    data = lifeos.select_data(PAYLOAD)
    assert data["recovery_series"] == [("2026-07-27", 71), ("2026-07-28", 82)]


def test_select_data_without_scores_raises():
    with pytest.raises(ValueError):
        lifeos.select_data({"days": [{"date": "2026-07-28", "recovery_score": None}]})


def test_patch_updates_whoop_fields():
    result, changes = lifeos.patch(DASHBOARD, lifeos.select_data(PAYLOAD))
    assert 'updated:"28.07.2026"' in result
    assert "recovery:82" in result
    assert "sleepPct:85" in result
    assert "sleepH:8.29" in result
    assert 'sleepWin:"23:32–07:59"' in result
    assert "strain:0.1" in result
    assert changes


def test_patch_leaves_other_sources_alone():
    result, _ = lifeos.patch(DASHBOARD, lifeos.select_data(PAYLOAD))
    assert 'weight:[["05.06.",81.05,13.4,0]]' in result
    assert 'activities:[["27.07.","Kraft",3,49]]' in result
    assert "weight:81.50" in result and "kfa:13.5" in result
    assert 'plan:"Lockerer Z2-Lauf, ruhig {kein JSON}"' in result
    assert "proteinTarget:203" in result


def test_patch_replaces_recovery_series():
    result, _ = lifeos.patch(DASHBOARD, lifeos.select_data(PAYLOAD))
    assert '["27.07.",71],["28.07.",82]' in result
    assert '["20.06.",11]' not in result


def test_patch_is_idempotent():
    once, _ = lifeos.patch(DASHBOARD, lifeos.select_data(PAYLOAD))
    twice, changes = lifeos.patch(once, lifeos.select_data(PAYLOAD))
    assert once == twice
    assert changes == []


def test_patch_without_today_block_raises():
    with pytest.raises(ValueError):
        lifeos.patch("const ATH = { recovery:[] };", lifeos.select_data(PAYLOAD))


def test_run_backs_up_before_writing(tmp_path):
    path = tmp_path / "index.html"
    path.write_text(DASHBOARD)
    result = lifeos.run(dashboard=path, payload=PAYLOAD)
    assert result["written"] is True
    backup = tmp_path / result["backup"].split("/")[-1]
    assert backup.read_text() == DASHBOARD
    assert "recovery:82" in path.read_text()


def test_run_uses_versions_folder_when_present(tmp_path):
    path = tmp_path / "index.html"
    path.write_text(DASHBOARD)
    (tmp_path / "versions").mkdir()
    result = lifeos.run(dashboard=path, payload=PAYLOAD)
    assert "/versions/" in result["backup"]


def test_dry_run_does_not_touch_the_file(tmp_path):
    path = tmp_path / "index.html"
    path.write_text(DASHBOARD)
    result = lifeos.run(dashboard=path, payload=PAYLOAD, dry_run=True)
    assert result["written"] is False
    assert path.read_text() == DASHBOARD
    assert result["changes"]


def test_missing_dashboard_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        lifeos.run(dashboard=tmp_path / "nope.html", payload=PAYLOAD)
