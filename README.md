# Schloss-Monitor – Hermes-Agent-Auftrag

Dieses Paket enthält **noch keinen implementierten Scraper**, sondern die fertigen Projektanweisungen, aus denen Hermes Agent das vollständige Python-Projekt erstellen soll.

## Welche Datei verwendet Hermes?

Hermes Agent lädt `AGENTS.md` als Projektkontext; alternativ sind `.hermes.md` oder `CLAUDE.md` möglich. Nutze hier `AGENTS.md` für Kompatibilität mit anderen Coding-Agenten. `PROJECT_SPEC.md` enthält die ausführlichen Anforderungen, die Hermes explizit lesen soll.

## So beginnst du

1. Alle Dateien dieses Pakets ins Root-Verzeichnis eines neuen Repositories kopieren.
2. Ein Terminal **im Projektordner** öffnen und Hermes Agent starten.
3. Folgenden Auftrag an Hermes senden:

> Lies `AGENTS.md` und `PROJECT_SPEC.md` vollständig. Setze das beschriebene Python-Projekt bis zur lauffähigen Version um, inklusive Playwright-Scraper, SQLite-Differenzvergleich, Konsolenausgabe, Tests, `.devcontainer`, `Dockerfile` und `compose.yaml`. Inspiziere zuerst die tatsächlichen DOM-Strukturen und die öffentliche Ticketanzeige. Führe Tests und Docker-Build aus. Kennzeichne unbekannte Restplatzanzahlen korrekt, statt Zahlen zu erfinden. Telegram bleibt deaktiviert. Dokumentiere verbleibende Einschränkungen.

4. Hermes soll die `config.example.toml` als Ausgangspunkt nach `config.toml` übernehmen und `.env.example` als Vorlage nutzen.

## Warum Playwright?

Die Ausgangsseite verfügt über „weitere Termine laden“, einzelne Veranstaltungs-Detailseiten und `buchen`-Links zu einer separaten Ticketseite. Browserautomatisierung bietet eine robuste Grundlage für diese Interaktionen. Wenn sich während der Inspektion eine offizielle, erlaubte Read-only-Datenquelle ergibt, kann Hermes sie nach dokumentierter Prüfung ergänzen.

## Warum SQLite?

Ein einzelner Monitor benötigt keinen separaten Server. SQLite merkt sich pro Datum und Uhrzeit den letzten bestätigten Bestand über Docker-Restarts hinweg, sodass nur Neuigkeiten und Änderungen ausgegeben werden.

## Wesentliche Einschränkung

Auf der Schloss-Website steht, dass der Terminkalender nicht mit dem Buchungsportal synchronisiert ist. Die konkrete freie Ticketzahl muss im öffentlichen Buchungsportal nachvollziehbar ermittelt werden. Nur die Tatsache, dass man „buchen“ klicken kann, beweist noch keine bestimmte Zahl freier Plätze.

## Geplante Bedienung *nach* Implementierung

```bash
# Einmalig, zum Testen
python -m schloss_monitor --once

# Unit-Tests
pytest

# Lint
ruff check .

# Container starten
docker compose up -d --build

# Live-Ausgabe verfolgen
docker compose logs -f monitor

# Container stoppen
docker compose down
```

Diese Befehle funktionieren erst, nachdem Hermes die im Auftrag geforderten Dateien und den Code erstellt hat.
