"""MCP-Server: stellt die WHOOP-Daten als Tools bereit."""

from __future__ import annotations

import json
from typing import Any

try:  # MCP SDK >= 2.0
    from mcp.server import MCPServer as _Server
except ImportError:  # MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from . import aggregate, lifeos as lifeos_module, normalize, sync as sync_module
from .client import WhoopClient
from .store import Store

mcp = _Server("whoop")

_client: WhoopClient | None = None
_store: Store | None = None


def get_client() -> WhoopClient:
    global _client
    if _client is None:
        _client = WhoopClient()
    return _client


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def _clamp(days: int, maximum: int = 365) -> int:
    return max(1, min(int(days), maximum))


@mcp.tool()
def whoop_summary(days: int = 7) -> dict[str, Any]:
    """Kombinierter Tagesueberblick: Recovery, Schlaf und Strain je Tag.

    Das Standard-Tool fuer Fragen wie "Wie war meine Woche?". Liefert pro Tag
    einen Datensatz plus Durchschnitte und Trends.
    """
    days = _clamp(days)
    client = get_client()
    recoveries = [normalize.recovery(r) for r in client.recoveries(days=days)]
    sleeps = [normalize.sleep(r) for r in client.sleeps(days=days)]
    cycles = [normalize.cycle(r) for r in client.cycles(days=days)]
    rows = aggregate.daily(recoveries, sleeps, cycles)
    return {
        "days_requested": days,
        "latest": rows[0] if rows else None,
        "daily": rows,
        "averages": aggregate.averages(rows),
    }


@mcp.tool()
def whoop_recovery(days: int = 7) -> dict[str, Any]:
    """Recovery Score, HRV, Ruhepuls, SpO2 und Hauttemperatur der letzten Tage."""
    days = _clamp(days)
    records = [normalize.recovery(r) for r in get_client().recoveries(days=days)]
    return {"days_requested": days, "count": len(records), "records": records}


@mcp.tool()
def whoop_sleep(days: int = 7) -> dict[str, Any]:
    """Schlafdauer, Schlafphasen, Performance, Konsistenz und Atemfrequenz."""
    days = _clamp(days)
    records = [normalize.sleep(r) for r in get_client().sleeps(days=days)]
    return {"days_requested": days, "count": len(records), "records": records}


@mcp.tool()
def whoop_cycles(days: int = 7) -> dict[str, Any]:
    """Tages-Strain, Kalorienverbrauch sowie durchschnittliche und maximale Herzfrequenz."""
    days = _clamp(days)
    records = [normalize.cycle(r) for r in get_client().cycles(days=days)]
    return {"days_requested": days, "count": len(records), "records": records}


@mcp.tool()
def whoop_workouts(days: int = 14, sport: str | None = None) -> dict[str, Any]:
    """Trainingseinheiten mit Strain, Herzfrequenzzonen, Distanz und Kalorien.

    Mit ``sport`` laesst sich auf eine Sportart filtern, etwa "running".
    """
    days = _clamp(days)
    records = [normalize.workout(r) for r in get_client().workouts(days=days)]
    if sport:
        needle = sport.lower()
        records = [r for r in records if (r.get("sport") or "").lower() == needle]
    return {"days_requested": days, "count": len(records), "records": records}


@mcp.tool()
def whoop_body() -> dict[str, Any]:
    """Koerpermasse aus WHOOP: Groesse, Gewicht und maximale Herzfrequenz."""
    return normalize.body(get_client().body_measurement())


@mcp.tool()
def whoop_history(days: int = 90, metric: str | None = None) -> dict[str, Any]:
    """Langfristige Auswertung aus der lokalen Datenbank statt aus der API.

    Schnell und ohne Rate-Limit, benoetigt aber einen vorherigen Sync. Mit
    ``metric`` (etwa "hrv_ms", "recovery_score", "strain", "asleep_hours")
    kommt zusaetzlich ein Trendvergleich zurueck.
    """
    days = _clamp(days, maximum=3650)
    store = get_store()
    recoveries = [
        normalize.recovery(json.loads(row["raw"])) for row in store.recent("recovery", days)
    ]
    sleeps = [normalize.sleep(json.loads(row["raw"])) for row in store.recent("sleep", days)]
    cycles = [normalize.cycle(json.loads(row["raw"])) for row in store.recent("cycles", days)]
    rows = aggregate.daily(recoveries, sleeps, cycles)
    result: dict[str, Any] = {
        "days_requested": days,
        "count": len(rows),
        "daily": rows,
        "averages": aggregate.averages(rows),
        "stored_totals": store.counts(),
        "last_sync": store.get_meta(sync_module.LAST_SYNC_KEY),
    }
    if metric:
        result["trend"] = aggregate.trend(rows, metric)
    return result


@mcp.tool()
def whoop_sync(days: int | None = None) -> dict[str, Any]:
    """Daten von WHOOP in die lokale Datenbank holen und den Life-OS-Export schreiben.

    Ohne ``days`` wird ab dem letzten Sync nachgeholt.
    """
    return sync_module.run(
        client=get_client(), store=get_store(), days=_clamp(days) if days else None
    )


@mcp.tool()
def whoop_lifeos_update(dry_run: bool = False) -> dict[str, Any]:
    """Recovery, Schlaf und Strain ins Life-OS-Dashboard schreiben.

    Aktualisiert nur die Whoop-Felder; Strava-Aktivitaeten, Gewicht und
    Ernaehrung bleiben unberuehrt. Vor dem Schreiben wird eine Sicherung
    angelegt. Mit ``dry_run`` werden die Aenderungen nur angezeigt.
    """
    try:
        return lifeos_module.run(dry_run=dry_run)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc)}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
