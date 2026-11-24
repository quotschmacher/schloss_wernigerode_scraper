# Schloss Wernigerode Terminmonitor

Read-only Monitor für die öffentlichen Termine der Führung **„Die Schule der magischen Tiere – Besichtigung Drehorte“** auf Schloss Wernigerode.

Der Monitor liest den öffentlichen Kalender, prüft pro buchbarem Einzeltermin die öffentlich verfügbare Ticketfritz-Antwort und speichert den letzten erfolgreich bestätigten Zustand in SQLite. Er reserviert, bucht oder bezahlt niemals Tickets.

> Dieses unabhängige Open-Source-Projekt steht in keiner Verbindung zu Schloss Wernigerode oder Ticketfritz. Öffentliche Webseiten und Datenquellen können sich ändern.

## Funktionen

- Playwright-Erfassung des dynamischen Kalenders inklusive „weitere Termine laden“.
- Mehrere Uhrzeiten eines Kalendertags werden getrennt überwacht.
- Exakte Restplatzzahlen nur aus expliziten Ticketfritz-Feldern (`AnzahlFrei`, `MengeAktuellVerfuegbar`).
- Keine Schätzung aus Kapazität, Warenkorb-Limit oder Preisstufe.
- SQLite-basierte Änderungserkennung für neue Termine, mehr/weniger Plätze, Ausbuchungen und unbekannte Mengen.
- Konsolenausgabe aller aktuell freien Termine nach jedem erfolgreichen Scan.
- Markierungen für `WOCHENENDE`, `FEIERTAG: <Name>` und `SCHULFERIEN: <Ferienart>`.
- Optionale Telegram-Alerts sowie `/scan`, `/list` und `/help`.
- Container-basierte Entwicklung, Tests und Betrieb; kein Host-Python erforderlich.

## Datenqualität und Grenzen

Der Schloss-Kalender und das Buchungsportal sind laut Website nicht zwingend synchron. Daher hat die öffentliche Ticketfritz-Antwort für die Restplatzzahl Vorrang.

| Beobachtung | Ergebnis |
|---|---|
| Explizite Restplatzzahl in Ticketfritz | `AVAILABLE` mit exakter Zahl |
| Detailseite meldet freie Plätze, Ticketfritz liefert keine verifizierbare Zahl | `AVAILABLE` mit unbekannter Zahl |
| Ticketfritz bestätigt ausverkauft | `SOLD_OUT` mit `0` |
| Technischer Fehler beim Kalender- oder Buchungszugriff | Scan schlägt fehl; der vorherige Snapshot bleibt unverändert |

Ein unbekannter Wert bedeutet **nicht** null freie Plätze.

## Schnellstart mit GHCR

Lege auf dem Server eine `compose.yaml` an:

```yaml
services:
  monitor:
    image: ghcr.io/quotschmacher/schloss_wernigerode_scraper:latest
    init: true
    restart: unless-stopped
    # Für Docker Desktop/Windows-Bind-Mounts erforderlich.
    user: "0:0"
    env_file:
      - .env
    environment:
      MONITOR_DB_PATH: /data/appointments.sqlite3
    volumes:
      - ./data:/data
```

Erstelle eine `.env` aus `.env.example`. Zugangsdaten gehören ausschließlich in diese lokale Datei.

```bash
mkdir -p data
docker compose pull
docker compose up -d
docker compose logs -f monitor
```

Jeder Push nach `main` veröffentlicht:

- `ghcr.io/quotschmacher/schloss_wernigerode_scraper:latest`
- `ghcr.io/quotschmacher/schloss_wernigerode_scraper:<vollständiger-commit-sha>`

Für reproduzierbare Deployments den vollständigen Commit-SHA verwenden.

> Immer `./data:/data` mounten, nie die einzelne SQLite-Datei. Eine fehlende Datei wird automatisch angelegt, sofern das Verzeichnis beschreibbar ist.

## Konfiguration

Priorität: CLI-Argumente → Umgebungsvariablen → `config.toml` → Defaults.

| Variable | Standard | Zweck |
|---|---:|---|
| `MONITOR_INTERVAL_SECONDS` | `3600` | Pause nach einem Scan |
| `MONITOR_DB_PATH` | `/data/appointments.sqlite3` | SQLite-Pfad im Container |
| `MONITOR_HEADLESS` | `true` | Chromium ohne Fenster |
| `MONITOR_LOG_LEVEL` | `INFO` | Log-Level |
| `MONITOR_REQUEST_DELAY_SECONDS` | `1.5` | Mindestpause zwischen Webzugriffen |
| `MONITOR_FEDERAL_STATE` | `sachsen-anhalt` | Ferien-URL-Slug, z. B. `berlin` |
| `MONITOR_TELEGRAM_ENABLED` | `false` | Telegram aktivieren |
| `MONITOR_TELEGRAM_COMMANDS_ENABLED` | `true` | Telegram-Kommandos aktivieren |
| `MONITOR_TELEGRAM_COMMAND_POLL_SECONDS` | `5` | Poll-Intervall für Kommandos |
| `TELEGRAM_BOT_TOKEN` | – | Bot-Token, niemals committen oder loggen |
| `TELEGRAM_CHAT_ID` | – | erlaubter Empfänger- und Kommandchat |

`.env.example` ist die sichere Vorlage für Laufzeitvariablen. `config.example.toml` wird beim Container-Build als Standardkonfiguration verwendet.

### Bundesländer für den Ferienabgleich

`MONITOR_FEDERAL_STATE` erwartet den URL-Slug von schulferien.org. Unterstützt werden:

| Bundesland | Wert |
|---|---|
| Baden-Württemberg | `baden-wuerttemberg` |
| Bayern | `bayern` |
| Berlin | `berlin` |
| Brandenburg | `brandenburg` |
| Bremen | `bremen` |
| Hamburg | `hamburg` |
| Hessen | `hessen` |
| Mecklenburg-Vorpommern | `mecklenburg-vorpommern` |
| Niedersachsen | `niedersachsen` |
| Nordrhein-Westfalen | `nordrhein-westfalen` |
| Rheinland-Pfalz | `rheinland-pfalz` |
| Saarland | `saarland` |
| Sachsen | `sachsen` |
| Sachsen-Anhalt | `sachsen-anhalt` |
| Schleswig-Holstein | `schleswig-holstein` |
| Thüringen | `thueringen` |

Der Ferienkalender wird nach einem erfolgreichen Termin-Scan geladen. Gesetzliche Feiertage werden lokal aus dem konfigurierten Bundesland berechnet; der 6. Januar 2027 wird beispielsweise in Sachsen-Anhalt als `FEIERTAG: Heilige Drei Könige` markiert. Fällt die Ferienquelle aus, bleiben Wochenend- und Feiertagsmarker verfügbar; der Termin-Scan selbst bleibt gültig.

## Telegram

Bei aktiviertem Telegram prüft der Start `getMe` und `getChat`; Tokenwerte werden nicht geloggt.

### Automatische Nachrichten

- `[NEU]`: neuer buchbarer Termin mit verifizierter Restplatzzahl.
- `[MEHR]`: erhöhte Restplatzzahl, inklusive `vorher → aktuell`.
- `[FEHLER] Scan fehlgeschlagen: …`: vollständiger Scan ist fehlgeschlagen.

Verringerungen, unbekannte Mengen und Ausbuchungen lösen keine automatischen Telegram-Alerts aus. Nachrichten über 4.096 Zeichen werden an vollständigen Terminblöcken geteilt.

### Kommandos

Nur das konfigurierte `TELEGRAM_CHAT_ID` kann Kommandos ausführen. Beim Start registriert der Bot die Befehle im Telegram-Kommandomenü; `/help` sendet zusätzlich persistente Buttons.

| Kommando | Wirkung |
|---|---|
| `/scan` | Fordert einen vollständigen Scan außerhalb des Intervalls an. Anschließend folgt `[OK]` oder `[FEHLER]`. Während eines laufenden Scans wird kein Folgescan vorgemerkt. |
| `/list` | Sendet den zuletzt erfolgreich gespeicherten freien SQLite-Bestand, inklusive der beim Scan gespeicherten Wochenend- und Ferienmarker. Kein Webzugriff. |
| `/help` | Zeigt Kurzbeschreibung und Buttons. |

## Entwicklung und Betrieb

Alle Python-Ausführungen laufen im Docker-Container. Auf dem Host werden weder Python, `pip`, Playwright noch eine virtuelle Umgebung benötigt.

```bash
# Entwicklungsimage mit Testwerkzeugen und Chromium bauen
docker compose --profile dev build dev

# Tests und Lint im Dev-Container
docker compose --profile dev run --rm dev pytest -q
docker compose --profile dev run --rm dev ruff check .

# Einmaliger Live-Scan
docker compose --profile dev run --rm dev python -m schloss_monitor --once

# Monitor aus lokalen Quellen starten
docker compose up -d --build monitor
docker compose logs -f monitor
docker compose down
```

In VS Code kann der Devcontainer über **Reopen in Container** geöffnet werden. Das Terminal läuft dann bereits im Container.

### Bewusster Live-Test mit frischem Zustand

Ein Reset lässt beim folgenden erfolgreichen Durchlauf alle freien Termine als neu erscheinen und kann bei aktivem Telegram echte Alerts auslösen.

```bash
rm -f data/appointments.sqlite3 data/appointments.sqlite3-shm data/appointments.sqlite3-wal
docker compose --profile dev run --rm dev python -m schloss_monitor --once
```

## Architektur

```text
Schloss-Kalender ──► Detailseiten ──► Ticketfritz getEvents
       │                    │                  │
       └────────────────────┴────► Monitor ────┼──► SQLite-Snapshot
                                                ├──► Konsole
                                                └──► Telegram
```

- `calendar_scraper.py`: Kalender und Pagination
- `detail_scraper.py`: Detailseiten, Zeiten und Buchungslinks
- `booking_scraper.py`: öffentliche Ticketfritz-Verfügbarkeit
- `school_holidays.py`: Wochenend- und Ferienmarker
- `storage.py`: SQLite-Snapshot, Änderungserkennung und Kommandostatus
- `telegram_commands.py`: `/scan`, `/list`, `/help`

## Sicherheit und verantwortungsvoller Betrieb

- Keine Reservierungen, Warenkörbe, Logins, Zahlungen oder CAPTCHA-Umgehung.
- Moderate Rate und begrenzte Wiederholungen.
- Bei 403, 429, CAPTCHA oder unvollständigen Antworten wird nichts umgangen.
- `.env`, `config.toml`, SQLite-Daten und Zertifikate sind durch `.gitignore` ausgeschlossen.
- Sicherheitslücken oder versehentlich veröffentlichte Geheimnisse nicht als öffentliches Issue melden. Siehe [SECURITY.md](SECURITY.md).

## Lizenz

MIT. Siehe [LICENSE](LICENSE).
