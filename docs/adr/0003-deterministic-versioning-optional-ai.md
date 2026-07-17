# ADR-0003: Deterministische versIe + optionele AI

- Status: geaccepteerd
- Datum: 2026-07-17

## Context

De vorige opzet gebruikte Google Gemini om het versienummer-verhaal, de changelog
en het Qlik-blok te genereren. Dat vereiste een `GEMINI_API_KEY` in elke repo,
was niet reproduceerbaar en kon in theorie ongeldige output geven.

## Besluit

1. **Versie is deterministisch** met rolling-digit carry: elke merge `dev -> main`
   verhoogt met één stap, waarbij elk segment overrolt bij 9:
   `v0.0.9 -> v0.1.0`, `v0.9.9 -> v1.0.0`. Berekend uit de laatste git-tag op
   `main`. Geen LLM bepaalt de versie.
2. **Changelog = de commits op `dev` sinds de laatste tag** (`git log <tag>..HEAD`),
   gegroepeerd op Conventional-Commit prefix wanneer aanwezig.
3. **Gemini is optioneel en alleen voor tekst-polish.** Zonder `GEMINI_API_KEY`
   werkt alles volledig deterministisch en zonder secret. Met key mag Gemini
   uitsluitend de proza van release-notes en de mutatietekst herformuleren; het
   Qlik-blok wordt daarna hervalideerd (zie [ADR-0002](0002-qlik-changelog-roundtrip.md)).

## Gevolgen

- Geen verplicht secret; reproduceerbare, idempotente runs.
- Kwaliteit van release-notes hangt af van de kwaliteit van commit-berichten
  (bewuste afweging).
- De rolling-digit carry wijkt bewust af van standaard SemVer.
