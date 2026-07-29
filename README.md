# whoop-mcp

Lokaler MCP-Server für die [WHOOP API v2](https://developer.whoop.com/api/).
Läuft vollständig auf dem eigenen Rechner: Recovery, Schlaf, Strain und
Workouts stehen in Claude als Tools zur Verfügung, ein täglicher Sync legt eine
lokale Historie an und schreibt einen JSON-Export fürs eigene Dashboard.

## Was es kann

| Tool | Zweck |
| --- | --- |
| `whoop_summary` | Kombinierter Tagesüberblick aus Recovery, Schlaf und Strain |
| `whoop_recovery` | Recovery Score, HRV, Ruhepuls, SpO2, Hauttemperatur |
| `whoop_sleep` | Dauer, Schlafphasen, Performance, Konsistenz, Atemfrequenz |
| `whoop_cycles` | Tages-Strain, Kalorien, Ø- und Maximalpuls |
| `whoop_workouts` | Trainings mit Strain, HF-Zonen, Distanz, Kalorien |
| `whoop_body` | Größe, Gewicht, maximale Herzfrequenz |
| `whoop_history` | Langzeitauswertung aus der lokalen Datenbank, mit Trendvergleich |
| `whoop_sync` | Daten abrufen, lokal speichern, Export schreiben |

Einheiten werden alltagstauglich umgerechnet: Millisekunden zu Stunden,
Kilojoule zu Kilokalorien, Meter zu Kilometern. Die Rohantworten bleiben in der
Datenbank erhalten.

## Voraussetzungen

Eine App im [WHOOP Developer Dashboard](https://developer-dashboard.whoop.com)
mit dieser Redirect URL:

```
http://localhost:8765/callback
```

und diesen Scopes:

```
offline  read:recovery  read:cycles  read:sleep  read:workout
read:body_measurement  read:profile
```

`offline` ist zwingend erforderlich — ohne diesen Scope gibt WHOOP keinen
Refresh Token heraus und die Verbindung müsste stündlich erneuert werden.

## Installation

```bash
git clone https://github.com/d00ennis/whoop-mcp.git
cd whoop-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Einrichtung

```bash
whoop-mcp setup     # Client ID und Secret hinterlegen (landen im Schlüsselbund)
whoop-mcp auth      # Browser öffnet sich, Zugriff einmal bestätigen
whoop-mcp sync      # erster Abruf, standardmäßig 90 Tage rückwirkend
whoop-mcp status    # Konfiguration und Datenbestand prüfen
```

## In Claude einbinden

In `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "whoop": {
      "command": "/PFAD/ZU/whoop-mcp/.venv/bin/whoop-mcp",
      "args": ["serve"]
    }
  }
}
```

Danach Claude neu starten.

## Täglicher Sync

Per `launchd` oder Cron, zum Beispiel jeden Morgen um 6:30 Uhr:

```
30 6 * * * /PFAD/ZU/whoop-mcp/.venv/bin/whoop-mcp sync >> ~/.whoop-mcp/sync.log 2>&1
```

## Wo die Daten liegen

| Was | Wo |
| --- | --- |
| Client ID, Secret, Tokens | macOS-Schlüsselbund (Dienst `whoop-mcp`) |
| Historie | `~/.whoop-mcp/whoop.db` (SQLite) |
| Export fürs Dashboard | `~/.whoop-mcp/whoop.json` |

Über `WHOOP_MCP_DATA_DIR` und `WHOOP_MCP_EXPORT_PATH` lassen sich Verzeichnis
und Exportpfad verlegen.

## Aufbau

```
config.py      Pfade, Scopes, Secret-Speicher (Schlüsselbund mit Datei-Fallback)
auth.py        OAuth-Flow, lokaler Callback-Server, Token-Rotation
client.py      HTTP-Client: Pagination, 401-Refresh, 429-Backoff
normalize.py   Rohantworten zu flachen Datensätzen mit sinnvollen Einheiten
aggregate.py   Tageszusammenführung, Durchschnitte, Trends
store.py       SQLite-Historie, idempotente Upserts
sync.py        Abgleich und JSON-Export
server.py      MCP-Tools
```

## Tests

```bash
pip install -e ".[dev]"
pytest
```

## Lizenz und Datenschutz

Private Nutzung. Es werden keine Daten an Dritte übertragen — siehe
[PRIVACY.md](PRIVACY.md).
