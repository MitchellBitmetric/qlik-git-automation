# Qlik Git Automation

Automatische changelog, documentatie en release-beheer voor Qlik Sense-applicaties die via Git worden gesynchroniseerd.

Bij elke **Pull Request / Merge Request** worden automatisch drie bestanden bijgewerkt:

- `CHANGELOG.md` — versiegeschiedenis in Keep a Changelog-formaat
- `README.md` — projectdocumentatie (alleen als dat nodig is)
- `Changelog.qvs` — het Qlik laadscript met een `/* Log & Version */` blok

Na een **merge naar main** wordt automatisch een nieuwe **release** aangemaakt met een opgehoogd versienummer.

---

## Inhoudsopgave

- [Vereisten](#vereisten)
- [Bestandsstructuur](#bestandsstructuur)
- [Installatie GitHub](#installatie-github)
- [Installatie GitLab](#installatie-gitlab)
- [Hoe het werkt](#hoe-het-werkt)
- [Versienummering](#versienummering)
- [Qlik Log & Version formaat](#qlik-log--version-formaat)
- [Veelgestelde vragen](#veelgestelde-vragen)

---

## Vereisten

| Onderdeel | Details |
|-----------|---------|
| **Google Gemini API-sleutel** | Gratis aan te maken via [aistudio.google.com](https://aistudio.google.com) — geen creditcard vereist |
| **Qlik Git-integratie** | Qlik Cloud met Git-sync ingeschakeld |
| **Qlik scriptbestanden** | Opgeslagen als `.qvs`-bestanden (standaard Qlik Cloud formaat) |
| **GitLab** (alleen GitLab) | Personal Access Token met `api` en `write_repository` scope |

---

## Bestandsstructuur

### GitHub
```
.github/
├── workflows/
│   └── pr-changelog.yml        ← GitHub Actions workflow
└── scripts/
    └── pr_automation.py        ← Automation script
```

### GitLab
```
.gitlab-ci.yml                  ← GitLab CI/CD pipeline (in root van repo)
scripts/
├── pr_automation.py            ← Automation script (draait bij MR)
└── create_release.py           ← Release script (draait na merge)
```

---

## Installatie GitHub

### Stap 1 — Bestanden plaatsen

Kopieer de volgende bestanden naar je repo:

```
.github/workflows/pr-changelog.yml
.github/scripts/pr_automation.py
```

### Stap 2 — Gemini API-sleutel aanmaken

1. Ga naar [aistudio.google.com](https://aistudio.google.com)
2. Klik op **Get API key → Create API key**
3. Kopieer de sleutel (`AIza...`)

### Stap 3 — Secret instellen in GitHub

Ga naar je repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Name | Value |
|------|-------|
| `GEMINI_API_KEY` | `AIza...` |

### Stap 4 — Actions inschakelen

Ga naar het tabblad **Actions** en schakel workflows in als dat gevraagd wordt.

### Stap 5 — Klaar

Maak een Pull Request naar `main` of `master`. De workflow start automatisch.

---

## Installatie GitLab

### Stap 1 — Bestanden plaatsen

Kopieer de volgende bestanden naar je repo:

```
.gitlab-ci.yml
scripts/pr_automation.py
scripts/create_release.py
```

### Stap 2 — Gemini API-sleutel aanmaken

1. Ga naar [aistudio.google.com](https://aistudio.google.com)
2. Klik op **Get API key → Create API key**
3. Kopieer de sleutel (`AIza...`)

### Stap 3 — Personal Access Token aanmaken

Ga naar **GitLab → jouw avatar → Edit profile → Access Tokens → Add new token**:

| Veld | Waarde |
|------|--------|
| Token name | `gitlab-ci-api` |
| Expiration | bijv. 1 jaar |
| Scopes | ✅ `api` ✅ `write_repository` |

Kopieer de token (`glpat-...`).

### Stap 4 — CI/CD variabelen instellen

Ga naar je project → **Settings → CI/CD → Variables**:

| Key | Value | Masked |
|-----|-------|--------|
| `GEMINI_API_KEY` | `AIza...` | ✅ |
| `GITLAB_API_TOKEN` | `glpat-...` | ✅ |

> **Let op:** als je branch als **Protected** is ingesteld in GitLab, zet dan ook de variabelen op Protected. Anders worden ze niet doorgegeven aan de pipeline.

### Stap 5 — Protected Tags instellen

Om automatisch git-tags aan te maken na een merge, moeten CI-jobs tags mogen pushen:

Ga naar **Settings → Repository → Protected tags → Add tag**:

| Tag name pattern | Allowed to create |
|-----------------|-------------------|
| `v*` | Maintainers + CI/CD |

### Stap 6 — Skipped pipelines instellen (optioneel maar aanbevolen)

Ga naar **Settings → Merge Requests → Merge checks** en vink aan:

☑️ **Skipped pipelines are considered successful**

Dit voorkomt dat je niet kunt mergen als de pipeline wordt overgeslagen.

### Stap 7 — Klaar

Maak een Merge Request naar `main` of `master`. De pipeline start automatisch.

---

## Hoe het werkt

### Bij een Pull Request / Merge Request

```
1. PR/MR wordt geopend of bijgewerkt
        │
        ▼
2. Versienummer berekenen
   Leest de laatste git-tag (bijv. v0.1.1)
   Berekent de volgende versie (→ v0.1.2)
        │
        ▼
3. Context verzamelen via API
   - Commit-berichten
   - Gewijzigde bestanden
   - Huidige CHANGELOG.md
   - Huidige README.md
        │
        ▼
4. Gemini aanroepen
   Genereert in één API-call:
   - Changelog-entry met versienummer v0.1.2
   - README-update (alleen als relevant)
   - Qlik Log & Version blok
        │
        ▼
5. Bestanden bijwerken
   - CHANGELOG.md  → nieuwe entry bovenaan
                     (bij herhaalde run: bestaande entry vervangen)
   - README.md     → alleen bijgewerkt als Gemini dat nodig vindt
   - Changelog.qvs → Log & Version blok vervangen of aangemaakt
        │
        ▼
6. Automatisch committen naar de PR/MR-branch
   Commit: "chore: automatisch changelog & docs bijgewerkt via MR !22"
```

### Na merge naar main (alleen GitLab)

```
1. Merge naar main voltooid
        │
        ▼
2. Versienummer ophalen uit CHANGELOG.md
   (hetzelfde nummer dat tijdens de MR was berekend)
        │
        ▼
3. Git-tag aanmaken en pushen (bijv. v0.1.2)
        │
        ▼
4. GitLab Release aanmaken via API
   - Naam: "Release v0.1.2"
   - Beschrijving: inhoud uit CHANGELOG.md + Qlik Log & Version blok
```

### Loop-beveiliging

De automation commit terug naar de branch, wat normaal een nieuwe pipeline zou triggeren. Dit wordt voorkomen doordat de pipeline controleert of de commit-auteur `gitlab-ci-bot` is en in dat geval direct succesvol afsluit (`exit 0`).

---

## Versienummering

Het versienummer volgt [Semantic Versioning](https://semver.org/) in het formaat `vMAJOR.MINOR.PATCH`.

De automation hoogt automatisch het **patch**-nummer op bij elke PR/MR:

```
v0.1.0 → v0.1.1 → v0.1.2 → v0.1.3 ...
```

**Handmatig een minor of major release maken:**
Maak zelf een tag aan in GitLab/GitHub (bijv. `v0.2.0` of `v1.0.0`). De automation pakt daar automatisch vanaf verder bij de volgende PR.

**Eerste keer (nog geen tags):**
Het script start automatisch bij `v0.1.0`.

---

## Qlik Log & Version formaat

Het script zoekt automatisch naar een Qlik scriptbestand met de Changelog-sectie via:

1. Een bestand genaamd `Changelog.qvs` of `changelog.qvs`
2. Elk `.qvs`-bestand met een `///$tab Changelog` header

Het gegenereerde blok volgt dit formaat:

```
/*---------------------------------------------------------------------------------------------------------------
Log & Version

Versienummer    Datum         Naam            Mutatie
---------------------------------------------------------------------------------------------------------------
0.1.2           2026-03-19    gebruikersnaam  Omschrijving van de wijziging
                                              Extra mutatieregel indien nodig
0.1.1           2026-03-10    gebruikersnaam  Vorige wijziging
---------------------------------------------------------------------------------------------------------------*/
```

Bestaande regels worden bij elke update **bewaard** en onder de nieuwe entry geplaatst.

---

## Veelgestelde vragen

**De pipeline vindt mijn Qlik scriptbestand niet.**
Zorg dat je Changelog-tab in Qlik is opgeslagen als `Changelog.qvs`, of dat het bestand een `///$tab Changelog` header bevat. Als het bestand niet gevonden wordt, slaat het script het blok op als `qlik_changelog_block.txt` zodat je het handmatig kunt toevoegen.

**De README wordt elke keer opnieuw gegenereerd terwijl dat niet nodig is.**
Gemini beoordeelt zelf of de README bijgewerkt moet worden op basis van de wijzigingen. Als de README onterecht wordt bijgewerkt, kun je in de prompt in `pr_automation.py` expliciet aangeven welke secties niet gewijzigd mogen worden.

**Ik wil het versienummer anders ophogen (minor in plaats van patch).**
Pas de functie `bump_patch` aan in `pr_automation.py` en `create_release.py`. Bijvoorbeeld voor minor: `return f"v{major}.{int(minor) + 1}.0"`.

**De pipeline mislukt met een 403-fout bij git push.**
Controleer of je Personal Access Token (GitLab) de scope `write_repository` heeft, en of de token is ingesteld als CI/CD variabele `GITLAB_API_TOKEN`.

**Kan ik dit ook gebruiken zonder Qlik?**
Ja. Als er geen `.qvs`-bestanden gevonden worden, worden alleen `CHANGELOG.md` en `README.md` bijgewerkt. Het Qlik-blok wordt dan opgeslagen als `qlik_changelog_block.txt`.
