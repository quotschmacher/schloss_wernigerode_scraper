# PROJECT_SPEC.md – Anforderungskatalog / Implementierungsauftrag

## 1. Ziel

Ein Python-Monitor prüft in einer Endlosschleife öffentliche Führungstermine für „Die Schule der magischen Tiere – Besichtigung Drehorte“ am Schloss Wernigerode und protokolliert **nur belegbare freie Restplätze bzw. Veränderungen** in der Konsole. Eine Telegram-Anbindung ist architektonisch vorgesehen, versendet in Version 1 aber **keine Nachrichten**.

**Einstieg:** <https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere#termine>

**Wichtige Tatsache:** Die Veranstaltungsseite weist darauf hin, dass ihr eigener Kalender und das externe Buchungsportal nicht synchron sind. Daher ist der Kalender eine Vorfilterung, die Ticketbuchungsseite die maßgebliche Quelle für konkret verfügbare Plätze. Das Ticketportal liegt offenbar unter `schloss-wernigerode.ticketfritz.de` – endgültige Links müssen im Browser aus den echten `buchen`-Elementen ermittelt werden.

## 2. Soll-Ablauf pro Scan

1. Browser öffnen, Einstiegsseite laden, Terminbereich auswählen. Cookie-Dialog nur falls erforderlich behandeln (datensparsam, keine Werbeeinwilligung nötig).
2. Bei Vorhandensein wiederholt auf **„weitere Termine laden“** klicken. Nach jedem Klick prüfen, dass neue Elemente erscheinen bzw. die Schaltfläche verschwindet. Erst fortfahren, wenn die Liste **vollständig** geladen ist. Wenn Ladefortschritt stagniert oder eine konfigurierbare Sicherheitsgrenze erreicht ist, Scan als **fehlgeschlagen** markieren.
3. Kalendereinträge erfassen und deduplizieren. Pro Eintrag Datum (mit Jahr), Titel, gegebenenfalls Uhrzeiten, Status-Text, Detail-URL extrahieren. Ausgebuchte Einträge (Text **„leider ausgebucht“**, normalisiert, case-insensitiv) nach dieser MVP-Anforderung überspringen.
4. Jeden übrigen Eintrag/dessen Detailseite nacheinander aufrufen. Ein Datum kann z. B. Termine um 10:30, 11:30, 13:00 und 14:00 enthalten.
5. Auf der Detailseite **jeden zeitbezogenen Abschnitt** einzeln auswerten. Nur bei Status **„noch Plätze frei“** den **zu genau dieser Uhrzeit gehörigen** `buchen`-Link benutzen. Ausgebuchte Slots überspringen und nicht mit buchbaren Slots vermischen.
6. Öffentliche Buchungsansicht dieses Slots lesen. Exakte Ticket-Restmenge nur aus einer belastbaren Anzeige oder nachvollziehbar bestätigten Read-only-Daten übernehmen. Sind lediglich auswählbare Menge, Obergrenze (auf der Webseite wird für diese Führung 18 genannt) oder `verfügbar` ohne Zahl sichtbar, ist die Anzahl **unbekannt**.
7. Aggregierte, nach Datum/Uhrzeit sortierte Ergebnisliste erzeugen. Strukturiertes Modell mit `event_key`, `start_at`, `status`, `available_places: int | None`, `detail_url`, `booking_url`, `observed_at`, `source_of_count`.
8. Ergebnis auf Vollständigkeit prüfen. Nur bei verlässlich erfolgreichem Scan mit SQLite vergleichen und den neuen Zustand atomar persistieren.
9. Änderungen ausgeben (siehe Abschnitt 4). Beim ersten erfolgreichen Scan jede tatsächlich verfügbare Einzelveranstaltung einmal ausgeben; falls exakte Zahl nicht ermittelbar ist, `Anzahl unbekannt` ausgeben, niemals raten.
10. Nach abgeschlossenem Scan die konfigurierte Zeit in Sekunden pausieren, dann von vorn beginnen. Bei Scanfehler ebenfalls mit Backoff warten, ohne zuvor gespeicherte Bestände zu überschreiben.

### Beispiel: gemischte Detailseite

| Slot | Detailstatus | Aktion |
|---|---|---|
| 10:30 | leider ausgebucht | überspringen |
| 11:30 | noch Plätze frei | `buchen` öffnen, Bestand prüfen |
| 13:00 | leider ausgebucht | überspringen |
| 14:00 | noch Plätze frei | `buchen` öffnen, Bestand prüfen |

Keinesfalls 11:30 und 14:00 unter einem einzigen Datensatz zusammenfassen.

## 3. Extraktion der freien Plätze – kritischer Explorationsschritt

**Vor der Implementierung live prüfen und dokumentieren:**

- Ist `buchen` ein gewöhnlicher Link, öffnet ein neues Tab, ein Modal oder eine eingebettete Ticketfritz-Ansicht? Browser-Navigation entsprechend behandeln.
- Wie wird der exakte Restbestand **tatsächlich** angezeigt? Möglicherweise in sichtbarem Text, als `max`-Wert, nach initialem Laden per Read-only-API oder gar nicht. Jede Quelle verifizieren.
- Ein möglicher Bestell-Limitwert oder die allgemeine Teilnehmerobergrenze ist **kein sicherer Nachweis** des vorhandenen Bestands.
- Nur lesen, **keine Kauf- oder Reservierungsaktionen** auslösen; insbesondere keine Warenkorb- oder Checkout-Schaltflächen betätigen, keine künstlichen Probebuchungen durchführen.
- Wenn keine vertrauenswürdige Quelle existiert: Verfügbarkeit mit `status=AVAILABLE`, `available_places=null`, `source_of_count=unknown` speichern. Im Protokoll ausdrücklich `? Plätze (nicht exakt ermittelbar)` angeben. Keine Mengen-Deltas berechnen, solange einer der Werte unbekannt ist.
- Wenn Buchungsportal und Kalender abweichen, hat das Ticketportal fachlich Vorrang. Statuswechsel nur aus tatsächlich verifizierten Quellen ableiten.
- Bei Zugriffssperre/CAPTCHA: dokumentieren, nicht umgehen.

## 4. Zustände und Änderungsereignisse

### Datenmodell

- **Eindeutige Terminidentität:** Kombination aus normiertem Veranstaltungskennzeichen (`magische-tiere`), lokalem Kalendertag und Uhrzeit `HH:MM`. Falls offizielle eindeutige Event-IDs vorhanden sind, zusätzlich speichern; volatile Buchungslinks nicht als alleinigen Primärschlüssel verwenden.
- **Status:** `AVAILABLE`, `SOLD_OUT`, `UNKNOWN`, optional `NO_LONGER_LISTED`/`SKIPPED` als klar getrennte Beobachtungszustände. **Zahl unbekannt** (`NULL`) ist nicht gleich **null freie Plätze** (`0`).
- **Zeit:** `start_at` in lokaler Zone `Europe/Berlin`; `first_seen_at`, `last_seen_at`, `last_changed_at` in UTC.
- **Quellen:** Detail- und Buchungslink; dokumentierte Quelle der verfügbaren Menge (falls vorhanden).

### Ausgabe bei erstem erfolgreichen Scan

- Alle belegbar freien Einzeltermine mit Uhrzeit, ggf. exakter Platzzahl, URL.
- Unbekannte Mengen deutlich kennzeichnen.
- Bei keinerlei freien Slots nur eine Scan-Zusammenfassung (`keine freien Termine gefunden`).

### Ausgabe bei späteren erfolgreichen Scans

| Ereignis | Wann? | Darstellung |
|---|---|---|
| `NEW` | bisher nicht bekannter buchbarer Einzeltermin | `[NEU] 08.11.2026 10:30 – 8 Plätze` |
| `INCREASED` | vorherige und neue Menge bekannt; neuer Wert größer | `[MEHR] ... 2 → 5` |
| `DECREASED` | vorherige und neue Menge bekannt; neuer Wert kleiner | `[WENIGER] ... 6 → 3` |
| `SOLD_OUT` | Ausbuchung verlässlich bestätigt | `[AUSGEBUCHT] ... 0 Plätze` |
| `NO_LONGER_LISTED` | vormals gelisteter Slot ist nach vollständig erfolgreicher Erfassung nicht mehr zu finden | `[ENTFALLEN/UNGEPRÜFT] ...` (nicht als ausgebucht deklarieren) |
| `COUNT_DISCOVERED` | vorher unbekannte, jetzt verlässlich bekannte Zahl | `[ANZAHL ERMITTELT] ... ? → 4` |
| `COUNT_UNKNOWN` | vorher bekannte, jetzt nicht sicher lesbare Zahl | Warnung, alten bestätigten Bestand nicht als neuen aktuellen Bestand verkaufen |
| `UNCHANGED` | keine relevante Änderung | im normalen Modus kein Termin-Einzel-Log |

**Besonderheit der Kalender-Vorfilterung:** Wenn ein bislang verfügbarer Tag in der Übersicht plötzlich als `leider ausgebucht` markiert ist, kann die Ausbuchung im Buchungsportal noch ungeprüft sein. Kennzeichne dies als `ÜBERSICHT AUSGEBUCHT / nicht verifiziert`, **nicht** automatisch als gesicherte Restmenge `0`. Der in Version 1 verlangte Filter darf dabei erhalten bleiben.

### Ausgabebeispiel

```text
2026-11-01T08:00:00+01:00 INFO scan start id=42
[NEU] 07.11.2026 10:30 – 8 Plätze frei – https://...
[WENIGER] 07.11.2026 13:00 – 6 → 3 Plätze – https://...
[ANZAHL UNBEKANNT] 08.11.2026 14:00 – buchbar, exakte Platzzahl nicht ermittelbar
2026-11-01T08:01:30+01:00 INFO scan finished id=42 days=27 slots=43 changes=3
2026-11-01T08:01:30+01:00 INFO next scan in 3600 seconds
```

Ausdrucksform ist beispielhaft; die angegebenen Termine/Zahlen sind **synthetische Testdaten**, keine geprüften Live-Bestände.

## 5. SQLite (Pflicht)

Nutze `sqlite3` ohne zusätzliche DB-Dienste. Vorschlag:

```sql
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS appointments (
  event_key TEXT PRIMARY KEY,
  event_date TEXT NOT NULL,
  event_time TEXT NOT NULL,
  status TEXT NOT NULL,
  available_places INTEGER NULL,
  detail_url TEXT NULL,
  booking_url TEXT NULL,
  count_source TEXT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  last_changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL,
  completed_at TEXT NULL,
  status TEXT NOT NULL,
  calendar_days INTEGER NOT NULL DEFAULT 0,
  slots_examined INTEGER NOT NULL DEFAULT 0,
  error_message TEXT NULL
);
```

- Schema darf für History/Status erweitert werden, aber keine unnötig komplexe Infrastruktur.
- Die DB muss Neustarts/Neu-Builds überleben (`./data:/data` oder benanntes Docker-Volume).
- Ein fehlgeschlagener Scan wird in `scan_runs` protokolliert, darf aber keine falsch-negative Veränderung in `appointments` auslösen.
- SQLite-Updates atomar ausführen und idempotent halten. Änderungen an demselben Bestand nicht bei jedem Restart erneut melden.
- Um Zahländerungen nachträglich nachvollziehen zu können, optional zusätzlich `appointment_changes` als Audit-Tabelle anlegen.

## 6. Konfiguration

Erzeuge eine `config.toml` mit sinnvollen Defaults (Datei ins Repository, keine Secrets):

```toml
[monitor]
interval_seconds = 3600
run_immediately = true
timezone = "Europe/Berlin"

[scraper]
url = "https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere#termine"
headless = true
navigation_timeout_ms = 30000
max_load_more_clicks = 100
request_delay_seconds = 1.5

[storage]
db_path = "data/appointments.sqlite3"

[logging]
level = "INFO"

[telegram]
enabled = false
```

Vorgesehene Overrides: `MONITOR_INTERVAL_SECONDS`, `MONITOR_DB_PATH`, `MONITOR_HEADLESS`, `MONITOR_LOG_LEVEL`, `MONITOR_REQUEST_DELAY_SECONDS`, `MONITOR_TELEGRAM_ENABLED`, ggf. `MONITOR_CONFIG_FILE`.

Validieren: Pause > 0, max clicks > 0, URLs erlaubtes Schema, Pfad beschreibbar, boolesche Umgebungsvariablen robust interpretieren. Vermeide hartkodierte Pause. Durch Compose setzen können, z. B.:

```yaml
services:
  monitor:
    build: .
    init: true
    restart: unless-stopped
    environment:
      MONITOR_INTERVAL_SECONDS: ${MONITOR_INTERVAL_SECONDS:-3600}
      MONITOR_DB_PATH: /data/appointments.sqlite3
      MONITOR_HEADLESS: "true"
      MONITOR_TELEGRAM_ENABLED: "false"
    volumes:
      - ./data:/data
```

Dies ist ein **Konfigurationsbeispiel**; Hermes muss eine vollständig lauffähige `compose.yaml` und einen zugehörigen `Dockerfile` entwickeln.

## 7. Dauerbetrieb / Shutdown

1. Startup → Initialisierung → vollständiger Scan.
2. `sleep(interval_seconds)` **nach** jedem Scan-Durchlauf; auf SIGTERM/SIGINT reaktionsfähig bleiben.
3. Wiederholung ohne feste Endzahl. Keine rekursiven Funktionsaufrufe, keine unnötigen Scheduler/Worker.
4. Vorübergehende Browser- oder Netzfehler loggen, begrenzt retryen und beim nächsten Intervall weiter versuchen. Kein hoher Anfrage-Durchsatz durch Crash-Loop.
5. Browser-Kontexte, Tabs, Datenbankverbindungen sauber schließen.
6. CLI `--once` führt **genau einen** Scan aus und liefert bei Fehler nonzero Exit-Code; sinnvoll für Entwicklung und Tests.
7. In der Standardansicht nur Zustandsänderungen und Scan-Zusammenfassungen loggen; im Debug-Modus zusätzliche Diagnosen.

## 8. Devcontainer / Docker

- VS-Code-kompatible `.devcontainer/devcontainer.json`, das den Docker-Compose-Service `dev` verwendet. Python 3.12+, Playwright/Chromium inkl. OS-Abhängigkeiten, `pytest` und `ruff` befinden sich **im Entwicklungs-Image**. Die Image-Targets `development` und `production` dürfen denselben Anwendungsstand nutzen.
- Abhängigkeiten und Browser werden beim **Docker-Image-Build** installiert, **keine venv/virtualenv/.venv** (weder auf dem Host noch im Container). `postCreateCommand` darf **keine** venv erzeugen und soll nichts mehr installieren. Keine `pip`, `pytest`, `ruff` oder Python-Ausführung auf dem Host.
- Devcontainer startet **keinen Endlosprozess** automatisch. **Im Devcontainer-Terminal** sind `python -m schloss_monitor --once`, `pytest` und `ruff check .` erlaubt, weil diese Befehle dort im Container laufen. Vom Host aus ausschließlich via `docker compose --profile dev run --rm dev ...`.
- Produktions-`Dockerfile` enthält Playwright-Browser und native Bibliotheken. Reproduzierbare Abhängigkeiten, sinnvoller nicht-root-Betrieb, keine nicht notwendigen Netzwerkports.
- `compose.yaml`: `monitor` (Standardservice mit `restart: unless-stopped`, Volume für `/data`, Environment-Overrides, `init: true`, stdout) sowie `dev` (Compose-Profil `dev`, Quellcode als Bind-Mount, interaktive Entwicklung, kein Endlosprozess). Nur `monitor` wird durch `docker compose up -d --build monitor` dauerhaft gestartet.
- README beschreibt `docker compose --profile dev build dev`, `docker compose --profile dev run --rm dev pytest -q`, `docker compose --profile dev run --rm dev ruff check .`, `docker compose --profile dev run --rm dev python -m schloss_monitor --once`, `docker compose up -d --build monitor`, `docker compose logs -f monitor`, `docker compose down` sowie Intervall-Overrides über `.env`. **Keine Host-Python-Befehle als Setup-/Testschritte.**

## 9. Telegram (noch ohne Versand)

- Implementiere Notifier-Protokoll/Interface, z. B. `Notifier.notify(changes: list[Change])`.
- `ConsoleNotifier` wird in v1 verwendet.
- `TelegramNotifier` **nur vorbereitet**: Klasse/Stubs/Konfiguration und spätere Nachrichtenformatierung; keine API-Calls, keine Background-Queue, kein Versand, kein versehentlich aktivierter Test.
- Künftige optionale Variablen: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` nur als Namen dokumentieren; keine Werte ins Repository und Telegram immer default OFF.

## 10. Tests und Akzeptanzkriterien

Erstelle unabhängige Tests für mindestens:

- [ ] Startseite mit ersten sieben Tagen, wiederholtes Nachladen und korrekt erkannter Endzustand.
- [ ] Load-more-Stagnation bzw. technische Fehler → unvollständiger Scan, **keine** Snapshot-Deltas.
- [ ] Ausgebuchte Kalendereinträge werden nicht unnötig im Detail geöffnet.
- [ ] Detailseite mit vier Uhrzeiten und gemischten Statuswerten: nur korrekte buchbare Slots werden verfolgt.
- [ ] Echte Jahreszahlen aus der Detail-URL/Datumsdarstellung, nicht aus `dd.mm.` frei geraten; Jahreswechsel funktioniert.
- [ ] „Noch Plätze frei“, aber Portal ohne exakte Zahl → `NULL` und Ausgabe „unbekannt“.
- [ ] Ticketmengen-Obergrenze ≠ sicherer Restbestand; keine Schätzungen.
- [ ] Erster DB-Scan → alle freien Slots, zweiter identischer Scan → keine Änderungsereignisse.
- [ ] Platzanzahl größer/kleiner sowie neuer Termin → passende Deltas.
- [ ] Eindeutig belegtes Ausgebucht / nicht mehr gelistet → getrennte Ereignisse.
- [ ] Fehlgeschlagener Teilscan darf den letzten gesicherten Bestand nicht überschreiben.
- [ ] Persistenz nach Neustart / idempotente SQLite-Migration.
- [ ] Konfiguration aus TOML und Override mit Compose-Env.
- [ ] `--once` beendet sich; Normalmodus wird durch SIGTERM sauber beendet.
- [ ] Telegram wird in keinem Test/Produktionsfall real kontaktiert.
- [ ] Docker-Images für Entwicklung und Produktion baubar; Devcontainer als Entwicklungsumgebung nutzbar; alle Tests/Lints im Container ausgeführt; keine `.venv` oder Host-Python-Installation.

### Live-Abnahme

Ein sorgfältig ausgeführter Live-Smoketest bestätigt den DOM-/Navigationsfluss mindestens bis zur Buchungsansicht eines tatsächlich buchbaren, aktuellen Slots. Falls es zum Testzeitpunkt keine buchbaren Plätze gibt, dokumentiere diese Grenze offen. Ein Programm, das zwar syntaktisch läuft, aber die echte Platzanzahl nicht nachweisbar ermitteln kann, darf **nicht** behaupten, exakte Mengen zu liefern.

## 11. Nichtziele (Version 1)

- Keine automatische Buchung, kein Checkout, keine Zahlung, keine Kontenanmeldung.
- Kein Dashboard, keine Web-API, keine E-Mail-, Telegram- oder Push-Nachrichten.
- Keine Mehrbenutzerverwaltung, kein Redis, keine Kubernetes-Infrastruktur.
- Kein Umgehen von Captchas/Anti-Bot-Schutz oder aggressives paralleles Scraping.

## 12. Umsetzungsempfehlung und Lieferumfang

1. **Spike:** echte DOM-Strukturen / Ticketzahl-Quelle ermitteln und in `docs/site-findings.md` festhalten.
2. Calendar + Detail + Booking Read-only-Parser mit Fixtures.
3. SQLite + Differenzen + reine Konsolenausgabe.
4. Endlosschleife + robuste Konfiguration + SIGTERM.
5. Devcontainer, Produktions-Dockerfile, Compose und README.
6. Tests/Live-Smoke, verbleibende Einschränkungen dokumentieren.

Am Ende muss ein Entwickler das Repository öffnen, Tests **im Devcontainer oder über `docker compose --profile dev run --rm dev ...`** starten und den Monitor mittels `docker compose up -d --build monitor` betreiben können. Auf dem Host sind dafür nur Docker/Compose und ein Editor erforderlich, weder lokales Python noch eine virtuelle Umgebung.
