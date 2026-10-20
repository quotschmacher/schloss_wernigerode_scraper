# Schloss Wernigerode Terminmonitor

Read-only Playwright monitor for the public appointments of “Die Schule der magischen Tiere – Besichtigung Drehorte”. Every successful scan prints the current free slots to the console, even when the SQLite snapshot has not changed. Change events remain available primarily for a future Telegram notifier. Telegram is architecturally prepared but is an enforced no-op: this version never sends a Telegram request.

## Welche Datei verwendet Hermes?

Hermes Agent lädt `AGENTS.md` als Projektkontext; alternativ sind `.hermes.md` oder `CLAUDE.md` möglich. Nutze hier `AGENTS.md` für Kompatibilität mit anderen Coding-Agenten. `PROJECT_SPEC.md` enthält die ausführlichen Anforderungen, die Hermes explizit lesen soll.

## So beginnst du

1. Alle Dateien dieses Pakets ins Root-Verzeichnis eines neuen Repositories kopieren.
2. Ein Terminal **im Projektordner** öffnen und Hermes Agent starten.
3. Folgenden Auftrag an Hermes senden:

> Lies `AGENTS.md` und `PROJECT_SPEC.md` vollständig. Setze das beschriebene Python-Projekt bis zur lauffähigen Version um, inklusive Playwright-Scraper, SQLite-Differenzvergleich, Konsolenausgabe, Tests, `.devcontainer`, `Dockerfile` und `compose.yaml`. Inspiziere zuerst die tatsächlichen DOM-Strukturen und die öffentliche Ticketanzeige. Führe Tests und Linter ausschließlich über Docker Compose bzw. im Devcontainer aus, installiere nichts auf dem Host und erstelle keine venv. Kennzeichne unbekannte Restplatzanzahlen korrekt, statt Zahlen zu erfinden. Telegram bleibt deaktiviert. Dokumentiere verbleibende Einschränkungen.

4. Hermes soll die `config.example.toml` als Ausgangspunkt nach `config.toml` übernehmen und `.env.example` als Vorlage nutzen.

## Warum Playwright?

Die Ausgangsseite verfügt über „weitere Termine laden“, einzelne Veranstaltungs-Detailseiten und `buchen`-Links zu einer separaten Ticketseite. Browserautomatisierung bietet eine robuste Grundlage für diese Interaktionen. Wenn sich während der Inspektion eine offizielle, erlaubte Read-only-Datenquelle ergibt, kann Hermes sie nach dokumentierter Prüfung ergänzen.

## Warum SQLite?

Ein einzelner Monitor benötigt keinen separaten Server. SQLite merkt sich pro Datum und Uhrzeit den letzten bestätigten Bestand über Docker-Restarts hinweg, während die Konsole bei jedem erfolgreichen Scan die aktuell freien Slots ausgibt.

## Wesentliche Einschränkung

Auf der Schloss-Website steht, dass der Terminkalender nicht mit dem Buchungsportal synchronisiert ist. Die konkrete freie Ticketzahl muss im öffentlichen Buchungsportal nachvollziehbar ermittelt werden. Nur die Tatsache, dass man „buchen“ klicken kann, beweist noch keine bestimmte Zahl freier Plätze.

## Geplante Bedienung *nach* Implementierung – ausschließlich in Docker

Auf dem Host wird **kein Python, pip, Playwright, pytest, ruff oder venv** benötigt. Die Befehle unten werden vom Host aus ausgeführt, starten aber alle Python-Prozesse im `dev`- bzw. `monitor`-Container.

```bash
# Entwicklungsimage inklusive Testtools/Chromium bauen
docker compose --profile dev build dev

# Unit-Tests ausschließlich im Entwicklungscontainer
docker compose --profile dev run --rm dev pytest -q

# Lint ausschließlich im Entwicklungscontainer
docker compose --profile dev run --rm dev ruff check .

# Einmaliger Live-Scan im Entwicklungscontainer
docker compose --profile dev run --rm dev python -m schloss_monitor --once

# Dauerbetrieb in der Produktion starten
docker compose up -d --build monitor

# Live-Ausgabe verfolgen
docker compose logs -f monitor

# Dauerbetrieb stoppen
docker compose down
```

Alternativ in VS Code **„Reopen in Container“** öffnen. Dort darfst du `pytest`, `ruff check .` oder `python -m schloss_monitor --once` direkt im **Devcontainer-Terminal** ausführen. Das ist kein Host-Python.

**Kein venv erstellen.** Entwicklungspakete gehören in den Build-Schritt des Entwicklungs-Docker-Images. Der Devcontainer nutzt den Compose-Service `dev` und startet beim Öffnen keinen Monitor.

The project is implemented. `dev` is the Compose-profiled development/test service. `monitor` persists SQLite at `./data/appointments.sqlite3` through the project-relative host bind mount `./data:/data`; it exposes no ports. The Compose service runs as root so the bind mount remains writable on Docker Desktop for Windows.

Configuration lives in `config.toml`; the supported environment overrides are `MONITOR_INTERVAL_SECONDS`, `MONITOR_DB_PATH`, `MONITOR_HEADLESS`, `MONITOR_LOG_LEVEL`, `MONITOR_REQUEST_DELAY_SECONDS`, `MONITOR_TELEGRAM_ENABLED`, and `MONITOR_CONFIG_FILE`. Copy `.env.example` to `.env` for Compose interpolation. The default scan interval is 3600 seconds.

Availability is exact only when Ticketfritz's observed read-only `getEvents` response supplies `AnzahlFrei` or `MengeAktuellVerfuegbar` for the matching time. Capacity, cart limits, and price maxima are never treated as availability. When no exact field is available, the monitor records and prints an explicitly unknown count. No reservation, cart, checkout, login, or payment interaction is implemented.

`docs/site-findings.md` documents the real DOM/network inspection from 19 October 2026, including live-flow limitations. Unit tests use stored fixtures and do not depend on the public sites.
