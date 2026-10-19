# AGENTS.md – Schloss Wernigerode Terminmonitor

## Auftrag

Entwickle ein dauerhaft laufendes, vollständig getestetes Python-Projekt zur Überwachung freier Plätze für die Führung **„Die Schule der magischen Tiere – Besichtigung Drehorte“** auf:

https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere#termine

Die fachlichen Anforderungen, Sonderfälle und Abnahmekriterien stehen verbindlich in [`PROJECT_SPEC.md`](PROJECT_SPEC.md). Lies diese Datei vor Implementierungsbeginn vollständig. Dieses `AGENTS.md` legt zusätzlich die Entwicklungsregeln und Architektur fest.

## Verbindliche Regel: Container-only-Entwicklung und -Tests

**Alle Python-Ausführungen, Paketinstallationen, Browser-Installationen, Tests, Linter und Live-Smoke-Tests MÜSSEN in Docker-Containern stattfinden.** Auf dem Host wird ausschließlich Docker/Compose und der Editor verwendet.

- **KEINE virtuelle Python-Umgebung (`venv`, `.venv`, `virtualenv`, Conda, Poetry-Env oder `uv venv`) anlegen – weder auf dem Host noch im Container.** Nutze den Python-Interpreter des Docker-Images und installiere Abhängigkeiten beim Image-Build (Dockerfile), getrennt nach Produktions- und Entwicklungsabhängigkeiten.
- **KEIN** `pip install`, `pytest`, `ruff`, `playwright install`, `python -m ...` oder Python-Skript direkt auf dem Host ausführen. Der Agent darf Docker-Befehle vom Host aufrufen, die diese Programme **innerhalb** des Containers ausführen.
- Baue einen `dev`-Service mit Compose-Profil `dev` (Quellcode-Bind-Mount, Entwicklungstools, Chromium, kein automatisch startender Monitor) sowie einen `monitor`-Service für den Dauerbetrieb. Der Devcontainer muss sich an den `dev`-Service anhängen (`.devcontainer/devcontainer.json` mit `dockerComposeFile`, `service`, `workspaceFolder`); IDE-Terminal und Debugger verwenden dessen Python.
- Entwicklungsabhängigkeiten und Browser werden **im Image-Build** installiert. `postCreateCommand` darf höchstens einen harmlosen Statuscheck ausführen, **keine venv-Erstellung und keine Abhängigkeitsinstallation auf dem Host**. Für produktionsnahe Tests können dieselben Anwendungsquellen in beiden Image-Targets verwendet werden.
- Nutze für jeden Test/Scan ausschließlich die folgenden Arten von Befehlen **vom Host aus** (Service-Namen entsprechend implementieren):

  ```bash
  docker compose --profile dev build dev
  docker compose --profile dev run --rm dev pytest -q
  docker compose --profile dev run --rm dev ruff check .
  docker compose --profile dev run --rm dev python -m schloss_monitor --once
  docker compose up -d --build monitor
  docker compose logs -f monitor
  ```

- **Im bereits geöffneten Devcontainer-Terminal** sind `pytest`, `ruff check .` und `python -m schloss_monitor --once` natürlich zulässig: Das Terminal läuft bereits im Container. Diese Befehle **nicht** in einem Host-Terminal ausführen.
- Host-`.venv`-Verzeichnisse dürfen nicht als implizite Voraussetzung entstehen oder verwendet werden. In `.gitignore` und `.dockerignore` ausschließen.
- Wenn Docker aktuell nicht erreichbar ist, den Blocker transparent dokumentieren; **nicht** eigenmächtig auf Host-Python oder eine virtuelle Umgebung ausweichen und Tests dann als erfolgreich melden.

## Arbeitsweise für Hermes Agent

1. Inspiziere zuerst die reale Website und mindestens eine geeignete Detail-/Buchungsseite im Browser. Ermittle echte DOM-Strukturen, Ladeverhalten und die Quelle der verfügbaren Ticketzahl. **Keine CSS-Selektoren, API-Endpunkte oder Ticketzahlen erfinden.** Dokumentiere die Ergebnisse in `docs/site-findings.md` mit Datum.
2. Lege eine kurze Implementierungsreihenfolge fest, implementiere anschließend eigenständig und teste jeden Teilschritt. Frage nicht wegen alltäglicher Architekturentscheidungen nach.
3. Implementiere in kleinen, verständlichen Modulen. Halte reines Parsing, Browsersteuerung, Zustandsspeicherung und Benachrichtigung voneinander getrennt.
4. Schreibe Tests mit gespeicherten, anonymisierten HTML-Fixtures/Mocks. Automatisierte Tests dürfen nicht von der Erreichbarkeit der Website abhängen. Ergänze optional einen ausdrücklich als Live-Test markierten Smoke-Test.
5. Führe vor Abschluss Tests und Linter **ausschließlich im Devcontainer oder per Docker Compose** sowie einen Docker-Build aus. Dokumentiere exakt, welche Live-Flows du prüfen konntest und welche noch nicht. Erfinde keine bestandenen Tests.
6. Aktualisiere die README mit konkreten **containerbasierten** Build-, Test-, Debug-, Devcontainer- und Docker-Compose-Befehlen; keine Host-Python-Installation dokumentieren.

## Technologievorgaben

- Python **3.12+**, `pyproject.toml`, typisierte Dataclasses oder Pydantic-Modelle, `pytest`, `ruff`.
- **Playwright mit Chromium** für dynamisches „weitere Termine laden“, Navigation und ggf. interaktive Buchungsansichten. Standardmäßig headless; lokal per Konfiguration sichtbar schaltbar.
- **SQLite** aus der Python-Standardbibliothek (`sqlite3`), persistent auf Docker-Volume. Kein Redis, kein PostgreSQL, kein unnötiger Webserver.
- Konfiguration in `config.toml`; gleichnamige Werte über Umgebungsvariablen überschreibbar. Dateien mit Secrets niemals committen.
- Python-Modul mit CLI, z. B. `python -m schloss_monitor --once` für einen Durchlauf und `python -m schloss_monitor` für den Dauerbetrieb.
- Standardausgabe/Logging auf stdout/stderr, geeignet für `docker compose logs -f`.
- Für spätere Telegram-Nachrichten vorbereitete Notifier-Schnittstelle; **in dieser Version keinerlei Telegram-Netzwerkanfragen versenden**.

## Geplante Projektstruktur

```text
.
├── AGENTS.md
├── PROJECT_SPEC.md
├── README.md
├── pyproject.toml
├── config.toml
├── .env.example
├── .gitignore
├── Dockerfile
├── compose.yaml
├── .dockerignore
├── .devcontainer/
│   ├── devcontainer.json
│   └── Dockerfile               # falls für Entwicklungsabhängigkeiten nötig
├── docs/
│   └── site-findings.md
├── src/schloss_monitor/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── models.py
│   ├── browser.py
│   ├── calendar_scraper.py
│   ├── detail_scraper.py
│   ├── booking_scraper.py
│   ├── storage.py
│   ├── changes.py
│   ├── monitor.py
│   └── notifiers/
│       ├── __init__.py
│       ├── base.py
│       ├── console.py
│       └── telegram.py         # NO-OP / nur Interface, nichts senden
└── tests/
    ├── fixtures/
    ├── test_calendar.py
    ├── test_details.py
    ├── test_booking.py
    ├── test_changes.py
    ├── test_storage.py
    └── test_config.py
```

Die Namen dürfen bei begründetem Bedarf abweichen; die klare Trennung der Verantwortlichkeiten ist Pflicht.

## Fachliche Regeln

- Zuerst auf der Hauptseite wiederholt „weitere Termine laden“ auslösen, bis die Schaltfläche zuverlässig nicht mehr verfügbar ist. Pro Klick auf neu geladene Einträge bzw. das Verschwinden des Buttons warten, nicht mit `sleep` auf gut Glück. Stagnations- und Obergrenze als Fehler behandeln, nicht stillschweigend als vollständigen Durchlauf.
- Kalendereinträge mit „leider ausgebucht“ gemäß Anforderung überspringen; bei allen übrigen die jeweilige Detailseite öffnen. Ein Kalendertag kann **mehrere Einzeltermine** enthalten.
- Auf Detailseiten jeden einzelnen Block mit „noch Plätze frei“ samt **korrespondierender Uhrzeit und zugehörigem Buchen-Link** identifizieren. Niemals einen pauschalen Seitenstatus auf alle Zeiten übertragen.
- Nur so weit in die öffentliche Buchungsoberfläche gehen, wie zum **lesenden** Ermitteln der Ticket-Verfügbarkeit nötig. Niemals Tickets reservieren, einen Warenkorb befüllen, bestellen oder bezahlen.
- Exakte Zahl nur melden, wenn eine **nachprüfbare, tatsächlich verfügbare Restplatzanzahl** erkennbar ist. Ein Dropdown-Maximum oder die allgemeine Teilnehmerobergrenze ist nicht automatisch der Restbestand. Sonst `UNKNOWN`, niemals `0` oder eine erfundene Zahl.
- Die Datenbank hält einen dauerhaften letzten verifizierten Zustand pro Einzeltermin (Datum + Uhrzeit + Veranstaltung). Erst nach einem **erfolgreich abgeschlossenen** Scan Vergleiche committen. Fehlerhafte/unvollständige Scans dürfen keine falschen „entfallen“-/„ausgebucht“-Meldungen auslösen.
- Beim allerersten erfolgreichen Scan alle bestätigten freien Termine ausgeben; danach standardmäßig nur Änderungen: neu, mehr Plätze, weniger Plätze, bestätigt ausgebucht und ggf. entfallen. Fehlende Daten nicht automatisch zu `0` umdeuten.
- Alle Zeiten in `Europe/Berlin` interpretieren; Zeitstempel in der DB vorzugsweise als UTC ISO 8601 speichern.
- Während der gesamten Verarbeitung respektvolle Request-Rate, ein Browser mit wiederverwendeten Sessions, Timeouts und begrenzte Retries. Bei 429/403/Captcha/fehlender Berechtigung nicht umgehen, sondern pausieren bzw. sauber melden.

## Laufzeit und Konfiguration

Konfigurationspräzedenz: CLI-Argumente (wenn vorhanden) > Umgebungsvariablen > `config.toml` > dokumentierte Defaults.

Mindestens diese Variablen unterstützen:

| Umgebungsvariable | Zweck |
|---|---|
| `MONITOR_INTERVAL_SECONDS` | Pause **nach Ende** eines Scan-Durchlaufs |
| `MONITOR_DB_PATH` | SQLite-Datenbankpfad (Produktion: `/data/appointments.sqlite3`) |
| `MONITOR_HEADLESS` | Playwright headless (`true`/`false`) |
| `MONITOR_LOG_LEVEL` | z. B. INFO/DEBUG |
| `MONITOR_REQUEST_DELAY_SECONDS` | Mindestpause zwischen Zugriffen/Interaktionen |
| `MONITOR_TELEGRAM_ENABLED` | fest standardmäßig `false`; in MVP kein Senden |

- Sofort beim Start einmal ausführen, erst danach konfigurierbare Dauer pausieren und erneut scannen (`scan → diff → persist → sleep → scan`). Keine Busy Loop.
- `SIGTERM`/`SIGINT` sauber verarbeiten, Browser/DB schließen. Docker `restart: unless-stopped`; Anwendung selbst soll bei normalen Einzelfehlern weiterlaufen.
- Für einmalige Scans im Devcontainer/Compose `--once`; für Deploy regulärer Dauerbetrieb. Niemals Host-Python für Tests verwenden.
- Devcontainer muss Terminal, Tests und Debugging ermöglichen. Beim Öffnen des Devcontainers **nicht automatisch den Endlos-Monitor starten**.
- Container darf ausschließlich benötigte Berechtigungen haben, DB auf ein Volume mounten, Logs nicht in ein ephemeres Container-Dateisystem schreiben.

## Qualität und Sicherheit

- Keine versteckten Fehler durch pauschale `except: pass`; strukturierte Logging-Ausgabe mit Scan-ID, Zeitpunkt, Quelle, erkannten Terminen und Fehlergrund.
- Die Parser-Selektion so kapseln, dass Änderungen der Website leicht repariert werden können.
- Tests insbesondere für mehrere Uhrzeiten pro Tag, gemischte Statuswerte, Datum über Jahresgrenzen, unbekannte Ticketzahlen, fehlgeschlagene Scans, Neu-/Mehr-/Weniger-/Ausgebucht-Übergänge und Docker-Konfigurations-Overrides.
- Keine Umgehung von CAPTCHA, Rate-Limits, Sperren oder Bezahlschranken. Vor intensiver Nutzung robots.txt/Nutzungsbedingungen beider Domains prüfen; moderate Standardfrequenz (z. B. ein vollständiger Scan pro Stunde).
- Änderungen an Anforderungen in `PROJECT_SPEC.md` und an Betriebsdetails in `README.md` synchron halten.

## Abschlusskriterien

Das Projekt gilt erst als fertig, wenn die Akzeptanzkriterien in `PROJECT_SPEC.md` erfüllt, die automatisierten Tests grün und Devcontainer/Compose dokumentiert sind. Unverifizierbare Ticketzahlen sollen ausdrücklich als Einschränkung genannt werden, nicht scheinbar korrekt aussehen.
