# ADR-0002: Round-trip-baar Qlik changelog-blok

- Status: geaccepteerd
- Datum: 2026-07-17

## Context

Het changelog-blok wordt in het Qlik-laadscriptbestand geïnjecteerd. Omdat het
via Gitoqlok terug de app in wordt gepulld (zie [ADR-0001](0001-gitoqlok-writeback-boundary.md)),
moet het **geldige Qlik-syntax** zijn: een latere pull mag het laadscript niet
breken.

## Besluit

Het blok is één Qlik-blokcommentaar: het begint met `/*`, eindigt met `*/` en
bevat nergens daarbinnen een voortijdige `*/`. De structuur (kop `Log & Version`,
scheidingslijnen, kolomkoppen) wordt **deterministisch** opgebouwd in
`core/qlik_block.py`.

Na elke (optionele) AI-bewerking wordt het blok opnieuw gevalideerd met
`is_valid_block()`. Faalt de validatie, dan valt het systeem terug op het
deterministisch gebouwde blok. Gebruikerstekst met `*/` wordt geneutraliseerd
naar `* /`.

## Gevolgen

- AI kan de leesbaarheid verbeteren maar het laadscript nooit corrumperen.
- Injectie is idempotent: bij herhaalde run op dezelfde versie wordt de bestaande
  regel niet gedupliceerd en het blok in-place vervangen.
- Bestaande versieregels blijven bewaard onder de nieuwe entry.
