"""Whoop-Werte in das Life-OS-Dashboard schreiben.

Das Dashboard ist eine einzelne HTML-Datei mit einem eingebetteten ``ATH``-
Objekt. Aus WHOOP stammen nur ``updated``, die Recovery-Reihe und die
Whoop-Felder in ``today``. ``activities`` (Strava), ``weight`` (Waage),
``nutrition`` und ``plan`` bleiben unangetastet.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .config import data_dir, export_path

DEFAULT_DASHBOARD = Path.home() / "Documents/Claude/Artifacts/lifeos-dashboard/index.html"
RECOVERY_DAYS = 40


def dashboard_path(override: str | Path | None = None) -> Path:
    import os

    if override:
        return Path(override)
    env = os.environ.get("WHOOP_MCP_DASHBOARD")
    return Path(env) if env else DEFAULT_DASHBOARD


def _matching(text: str, start: int, opener: str, closer: str) -> int:
    """Index hinter der schliessenden Klammer zum Oeffner an ``start``."""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError(f"Keine schliessende Klammer '{closer}' ab Position {start} gefunden.")


def _de_date(iso_date: str, with_year: bool = False) -> str:
    day = datetime.strptime(iso_date, "%Y-%m-%d")
    return day.strftime("%d.%m.%Y") if with_year else day.strftime("%d.%m.")


def _num(value) -> str:
    if isinstance(value, float) and value != int(value):
        return f"{value:g}"
    return str(int(value)) if isinstance(value, (int, float)) else "0"


def select_data(payload: dict, days: int = RECOVERY_DAYS) -> dict:
    """Aus dem Export die Felder ziehen, die ins Dashboard gehoeren."""
    rows = payload.get("days") or []
    scored = [r for r in rows if isinstance(r.get("recovery_score"), (int, float))]
    if not scored:
        raise ValueError("Keine bewerteten Recovery-Tage im Export gefunden.")
    today = scored[0]

    series = [r for r in scored[:days]]
    series.reverse()  # Dashboard erwartet chronologisch aufsteigend

    return {
        "updated": today["date"],
        "today": {
            "recovery": today.get("recovery_score"),
            "sleepPct": today.get("sleep_performance_percent"),
            "sleepH": today.get("asleep_hours"),
            "sleepWin": today.get("sleep_window"),
            "strain": today.get("strain"),
        },
        "recovery_series": [(r["date"], r["recovery_score"]) for r in series],
    }


def _replace_scalar(block: str, key: str, value, changes: list, quoted: bool = False) -> str:
    if value is None:
        return block
    if quoted:
        pattern = re.compile(rf'(\b{key}\s*:\s*")([^"]*)(")')
        replacement = str(value)
    else:
        pattern = re.compile(rf"(\b{key}\s*:\s*)(-?[\d.]+)")
        replacement = _num(value)

    match = pattern.search(block)
    if not match:
        changes.append(f"{key}: nicht gefunden, uebersprungen")
        return block
    if match.group(2) == replacement:
        return block
    changes.append(f"{key}: {match.group(2)} -> {replacement}")
    return block[: match.start()] + match.group(1) + replacement + (
        '"' if quoted else ""
    ) + block[match.end():]


def patch(html: str, data: dict) -> tuple[str, list[str]]:
    """Reine Funktion: liefert neues HTML und eine Liste der Aenderungen."""
    changes: list[str] = []

    # updated:"28.07.2026"
    updated = _de_date(data["updated"], with_year=True)
    match = re.search(r'(\bupdated\s*:\s*")([^"]*)(")', html)
    if match and match.group(2) != updated:
        changes.append(f"updated: {match.group(2)} -> {updated}")
        html = html[: match.start()] + f'updated:"{updated}"' + html[match.end():]

    # today:{ ... } - nur die Whoop-Felder, plan/weight/kfa bleiben stehen
    today_match = re.search(r"\btoday\s*:\s*\{", html)
    if not today_match:
        raise ValueError("Kein today-Block im Dashboard gefunden.")
    start = html.index("{", today_match.start())
    end = _matching(html, start, "{", "}")
    block = html[start:end]
    for key, quoted in (
        ("recovery", False),
        ("sleepPct", False),
        ("sleepH", False),
        ("sleepWin", True),
        ("strain", False),
    ):
        block = _replace_scalar(block, key, data["today"].get(key), changes, quoted)
    html = html[:start] + block + html[end:]

    # recovery:[ ["20.06.",11], ... ]
    series_match = re.search(r"\brecovery\s*:\s*\[", html)
    if not series_match:
        raise ValueError("Keine recovery-Reihe im Dashboard gefunden.")
    start = html.index("[", series_match.start())
    end = _matching(html, start, "[", "]")
    entries = ",".join(
        f'["{_de_date(day)}",{_num(score)}]' for day, score in data["recovery_series"]
    )
    rendered = "[\n    " + entries + "\n  ]"
    if html[start:end] != rendered:
        old_count = html[start:end].count("[") - 1
        changes.append(
            f"recovery-Reihe: {old_count} -> {len(data['recovery_series'])} Eintraege"
        )
        html = html[:start] + rendered + html[end:]

    return html, changes


def backup(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    versions = path.parent / "versions"
    target = (
        versions / f"{path.stem}-whoop-{stamp}{path.suffix}"
        if versions.is_dir()
        else path.with_name(f"{path.stem}.bak-{stamp}{path.suffix}")
    )
    shutil.copy2(path, target)
    return target


def run(
    dashboard: str | Path | None = None,
    payload: dict | None = None,
    dry_run: bool = False,
) -> dict:
    path = dashboard_path(dashboard)
    if not path.exists():
        raise FileNotFoundError(f"Dashboard nicht gefunden: {path}")

    if payload is None:
        source = export_path()
        if not source.exists():
            raise FileNotFoundError(
                f"Kein Export vorhanden: {source}. Bitte zuerst 'whoop-mcp sync' ausfuehren."
            )
        payload = json.loads(source.read_text())

    data = select_data(payload)
    original = path.read_text()
    updated, changes = patch(original, data)

    result = {
        "dashboard": str(path),
        "day": data["updated"],
        "changes": changes,
        "written": False,
    }
    if dry_run or updated == original:
        return result

    result["backup"] = str(backup(path))
    path.write_text(updated)
    result["written"] = True

    marker = data_dir() / "lifeos-last-write.json"
    marker.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return result
