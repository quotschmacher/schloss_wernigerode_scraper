# Beitragen

Vielen Dank für Beiträge.

## Entwicklungsregeln

Dieses Projekt wird ausschließlich containerbasiert entwickelt:

- Kein Host-Python, kein Host-`pip` und keine virtuelle Umgebung.
- Abhängigkeiten werden im Docker-Image installiert.
- Tests und Lint laufen im Compose-Service `dev` oder im Devcontainer.
- Keine echten Tokens, Chat-IDs, SQLite-Dateien oder lokale Konfiguration committen.

## Lokales Prüfen

```bash
docker compose --profile dev build dev
docker compose --profile dev run --rm dev pytest -q
docker compose --profile dev run --rm dev ruff check .
```

## Pull Requests

1. Änderungen klein und thematisch begrenzt halten.
2. Neue Funktionen und Fehlerkorrekturen mit Tests absichern.
3. Dokumentation und `.env.example` aktualisieren, wenn sich Bedienung oder Konfiguration ändern.
4. Keine Kauf-, Reservierungs-, Login- oder CAPTCHA-Umgehungslogik hinzufügen.
5. Für Scraper-Anpassungen gespeicherte HTML-/JSON-Fixtures bevorzugen; Tests dürfen nicht von der öffentlichen Website abhängen.

## Meldungen und Fragen

Für Fehlerberichte bitte Version bzw. Commit-SHA, relevante anonymisierte Logs und klare Reproduktionsschritte angeben. Sicherheitsrelevante Themen gehören nicht in öffentliche Issues; siehe [SECURITY.md](SECURITY.md).
