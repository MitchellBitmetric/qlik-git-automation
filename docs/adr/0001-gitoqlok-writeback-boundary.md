# ADR-0001: Gitoqlok write-back grens

- Status: geaccepteerd
- Datum: 2026-07-17

## Context

Qlik-apps worden met **Gitoqlok** (Motio Chrome-extensie) vanuit de Qlik Sense UI
naar Git gecommit. Gitoqlok serialiseert het laadscript en app-objecten naar
bestanden in de repo. Onze automatisering draait in CI en werkt het
Qlik-laadscript**bestand** bij met een changelog-blok.

De vraag: mag/kan CI de wijziging ook terugschrijven naar de *live* Qlik-app?

## Besluit

Nee. **CI wijzigt uitsluitend het bestand in Git.** Er wordt geen qlik-cli en
geen Qlik API aangeroepen. Het injecteren van het changelog-blok in de draaiende
app gebeurt door de gebruiker via een **Gitoqlok pull** in de browser.

## Redenen

- Gitoqlok is de enige geautoriseerde brug tussen Git en de app; CI heeft geen
  (en hoeft geen) Qlik-credentials.
- Eén schrijfrichting per systeem voorkomt conflicten en dubbele bronnen van
  waarheid.
- Het houdt de automatisering platform-neutraal (GitHub én GitLab) en secret-arm.

## Gevolgen

- Het changelog-blok verschijnt pas in de app nadat iemand in Gitoqlok pullt.
- Het geïnjecteerde blok moet daarom een geldig, round-trip-baar Qlik-commentaar
  zijn (zie [ADR-0002](0002-qlik-changelog-roundtrip.md)).
