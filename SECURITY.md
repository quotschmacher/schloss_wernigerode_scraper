# Sicherheitsrichtlinie

## Unterstützte Version

Sicherheitskorrekturen werden für den jeweils aktuellen Stand auf `main` bereitgestellt.

## Sicherheitslücke melden

Bitte keine Sicherheitslücken, Zugangsdaten oder private Deployments als öffentliches GitHub-Issue veröffentlichen.

Nutze stattdessen eine private GitHub Security Advisory, sofern sie für das Repository verfügbar ist, oder kontaktiere den Repository-Eigentümer direkt über GitHub. Bitte beschreibe:

- betroffene Version bzw. Commit-SHA,
- reproduzierbare Schritte,
- mögliche Auswirkungen,
- und gegebenenfalls einen minimalen Fix-Vorschlag.

## Umgang mit Geheimnissen

- Bot-Token, Chat-IDs, `.env`-Dateien, `config.toml`, SQLite-Daten und Zertifikate dürfen nicht committed werden.
- Bei einer versehentlichen Veröffentlichung eines Tokens: Token sofort bei Telegram widerrufen/rotieren, alle betroffenen Deployments aktualisieren und die Git-Historie prüfen.
- Logs, Screenshots und Issues vor dem Veröffentlichen auf URLs, Chat-IDs und sonstige personenbezogene Daten prüfen.
