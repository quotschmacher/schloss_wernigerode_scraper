# Site findings

Live inspection: 19 October 2026 (read-only browser session)

## Scope and safety

The inspection used the public Schloss Wernigerode calendar, one public detail page, and its linked public Ticketfritz page. No cart, quantity selector, reservation, checkout, login, or payment action was used. The Ticketfritz cookie banner was confirmed with only the necessary-cookie option; optional cookies were left disabled.

The Schloss site's `/robots.txt` returned a TYPO3 404 page at the time of inspection. Ticketfritz's `/robots.txt` allowed robots generally and disallowed only `/TLS/`. This project nevertheless uses a deliberately low scan frequency and does not attempt to bypass access controls.

## Calendar page

Entry URL:

```text
https://www.schloss-wernigerode.de/kalender/die-schule-der-magischen-tiere#termine
```

Observed DOM structure:

- The calendar list container is `#eventlist`.
- Each day is an `a.eventLink` linking to a real relative detail URL such as `/kalender/detail/die-schule-der-magischen-tiere/10-11-2026`.
- The card contains `.event`, `.label.ausgebucht` (when present), `.datum`, `.eckdaten h2`, and `.uhrzeiten`.
- The initial page contained seven entries.
- The load-more control is `a#weitereTermineLaden.button.hoverLine`, with the text `weitere Termine laden`.
- After one click, the browser fetched this observed endpoint and the detail-link count grew from 7 to 14:

```text
https://www.schloss-wernigerode.de/?id=341&type=1742911569&tx_schlossevents_eventterminliste[pos]=7
```

The implementation must not hard-code the observed `id`, `type`, or `pos` values. It uses Playwright to click the real control and waits for an increased `a.eventLink` count or disappearance of the control. Repeated failure to make progress and the configured click limit are scan failures.

## Detail page

Inspected detail URL:

```text
https://www.schloss-wernigerode.de/kalender/detail/die-schule-der-magischen-tiere/10-11-2026
```

Observed DOM structure:

- The fully dated German heading is in `#detailHeader`.
- Individual appointment blocks are `#eventTermine .eventTermin`.
- Per-block status is `.plaetze .inner`.
- Per-block time is `.uhrzeit`.
- The matching external booking URL is `a.buchen` in the same `.eventTermin` block. It is a normal link with `target="_blank"`, not a modal or embedded frame.

This page had one block with `noch Plätze frei`, `11:30 Uhr`, and this live booking URL:

```text
https://schloss-wernigerode.ticketfritz.de/Event/Kalender/31935/59065?typ=Vorlage
```

The page also states that the calendar is not synchronized with the booking portal, so the booking portal takes precedence.

## Ticketfritz booking page and exact count

The inspected public Ticketfritz page loaded a visible event table with the `Plätze` column. Its initial DOM showed `18`. More importantly, browser network inspection showed that the page itself makes a read-only same-origin request after loading:

```text
/Event/getEvents?ZeitpunktVon=2026-11-10&ZeitpunktBis=2026-11-10&Typ=Vorlage&Wert=&VorlageOid=31935
```

The observed response was JSON served with `text/html; charset=utf-8`. For the one inspected event it included, among other fields:

```json
{
  "Ausverkauft": false,
  "AnzahlKapazitaet": 18,
  "AnzahlFrei": 18,
  "MengeAktuellVerfuegbar": 18,
  "CapacityTotal": 18,
  "ZeitpunktBezeichnung": "10.11.2026 - 11:30"
}
```

`AnzahlFrei` and `MengeAktuellVerfuegbar` are the only observed fields treated as an exact remaining-count candidate. The implementation requires a non-negative integer field and matches it to the requested date/time before recording it. It never uses `AnzahlKapazitaet`, `CapacityTotal`, `MaxWarenkorbMenge`, or price-level `MaxMenge` as a fallback count: those fields can represent capacity or a purchase limit rather than availability.

At the time of inspection all three relevant values happened to be 18, so the visual table alone could not prove that it was not showing capacity. The monitored program therefore records an exact count only from the explicitly named availability fields in the public response, otherwise it records `available_places = null` with source `unknown`.

## Live-flow limits

- A real calendar → detail → Ticketfritz navigation flow was verified for currently bookable calendar slots.
- The public JSON availability response was verified without interacting with any purchase controls.
- On 20 October 2026, the containerized monitor completed a full calendar-pagination run (23 calendar-day cards), reached the end state, and completed a SQLite-backed scan with four currently bookable slots. The output is intentionally not recorded here as a durable availability claim because those values change continuously.
- No CAPTCHA/403/429 response or mixed-status live detail page was available for safe live verification. Those cases are implemented and covered with stored fixtures/tests rather than claimed as live-tested.
