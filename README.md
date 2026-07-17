# Qlik Git Automation

Automatische versionering, changelog en releases voor **Gitoqlok**-beheerde Qlik
Sense-apps — identiek op **GitHub** en **GitLab**.

Gitoqlok (de Motio Chrome-extensie) commit vanuit de Qlik Sense UI het laadscript
en de app-objecten naar Git. Deze automatisering bouwt daar bovenop: bij een
merge `dev -> main` bepaalt de pipeline de volgende versie, bouwt de release-notes
uit de commits, en injecteert een geldig **`/* Log & Version */`** blok in het
Qlik-laadscript**bestand** — dat via een latere Gitoqlok *pull* weer in de app komt.

> **Write-back grens:** CI raakt alleen het bestand in Git aan. De app bijwerken
> doe je via Gitoqlok in de browser — nooit vanuit CI. Zie
> [ADR-0001](docs/adr/0001-gitoqlok-writeback-boundary.md).

---

## Inhoud

- [Hoe het werkt](#hoe-het-werkt)
- [Branchmodel](#branchmodel)
- [Versienummering](#versienummering)
- [Configuratie](#configuratie-één-bestand)
- [Installatie GitHub](#installatie-github)
- [Installatie GitLab](#installatie-gitlab)
- [Qlik Log & Version formaat](#qlik-log--version-formaat)
- [Optionele AI-polish](#optionele-ai-polish)
- [Architectuur](#architectuur)
- [FAQ](#faq)

---

## Hoe het werkt

```
feature/*  --PR-->  dev  --merge-->  main
                     │                  │
              changelog-preview   RELEASE-flow (qlik_release.py)
              (qlik_preview.py)   1. volgende versie (carry vanaf laatste tag)
                                  2. commits sinds laatste tag verzamelen
                                  3. CHANGELOG.md + release-notes + Qlik-blok bouwen
                                  4. (optioneel) AI-polish -> hervalideren
                                  5. bestanden bijwerken + terugcommit naar main
                                  6. git-tag + release aanmaken
```

- **Deterministisch:** geen AI nodig voor versie of changelog. Reproduceerbaar en
  idempotent (dezelfde versie tweemaal draaien doet niets extra's).
- **Portable:** één set scripts (`scripts/`) draait op beide platforms; alleen de
  dunne CI-configs en een kleine platform-adapter verschillen.

## Branchmodel

| Branch | Doel |
|--------|------|
| `main` | beschermd; **alleen releases** (merge vanaf `dev`) |
| `dev` | integratie; hier mergen `feature/*` branches |
| `feature/*` | losse wijzigingen vanuit Gitoqlok |

Instellen van branch protection: zie [docs/branch-protection.md](docs/branch-protection.md).
`init_repo.py` maakt `dev` aan en zet best-effort protection bij het seeden van een repo.

## Versienummering

Rolling-digit carry — elke merge `dev -> main` verhoogt met één stap, elk segment
rolt over bij 9:

```
v0.0.8 → v0.0.9 → v0.1.0 → ... → v0.9.9 → v1.0.0
```

Zonder tags start het bij `initial_version` (standaard `v0.0.1`). Zie
[ADR-0003](docs/adr/0003-deterministic-versioning-optional-ai.md).

## Configuratie (één bestand)

Kopieer [`qlik-release.example.yml`](qlik-release.example.yml) naar de root van je
repo als `qlik-release.yml` en pas alleen aan wat afwijkt. Alles is optioneel:

```yaml
main_branch: main
dev_branch: dev
load_script:
  path: ""                      # expliciet pad wint; leeg = auto-detectie
  glob: ["**/Changelog.qvs", "**/*changelog*.qvs"]
  tab_marker: "Changelog"       # matcht ///$tab ...Changelog
initial_version: "v0.0.1"
ai:
  polish: [release_notes, qlik_block]   # alleen bij aanwezige GEMINI_API_KEY
```

## Installatie GitHub

1. Plaats twee dunne caller-workflows in je repo (of laat `init_repo.py` dit doen):

   `.github/workflows/pr-changelog.yml`
   ```yaml
   on: { pull_request: { branches: [dev] } }
   jobs:
     preview:
       uses: bitmetric-bv/qlik-git-automation/.github/workflows/pr-changelog.yml@main
       secrets: inherit
   ```

   `.github/workflows/release.yml`
   ```yaml
   on: { push: { branches: [main] } }
   jobs:
     release:
       if: ${{ !contains(github.event.head_commit.message, '[skip release]') }}
       uses: bitmetric-bv/qlik-git-automation/.github/workflows/release.yml@main
       secrets: inherit
   ```

2. Kopieer `qlik-release.yml` in de root (optioneel; anders gelden defaults).
3. (optioneel) Zet secret `GEMINI_API_KEY` voor AI-polish.
4. Stel branch protection in — zie [docs/branch-protection.md](docs/branch-protection.md).

## Installatie GitLab

1. Voeg in de root van je repo een `.gitlab-ci.yml` toe die de template include't:

   ```yaml
   include:
     - project: 'bitmetric-bv/qlik-git-automation'
       file: '/.gitlab-ci.yml'
       ref: main
   ```

2. Kopieer `qlik-release.yml` in de root (optioneel).
3. **Settings → CI/CD → Variables:** `GITLAB_API_TOKEN` (PAT met `api` +
   `write_repository`), optioneel `GEMINI_API_KEY`. Protected indien de branch dat is.
4. **Protected tags:** patroon `v*` → Maintainers + CI/CD.
5. Branch protection — zie [docs/branch-protection.md](docs/branch-protection.md).

## Qlik Log & Version formaat

Het geïnjecteerde blok is een geldig Qlik-blokcommentaar (round-trip-baar):

```
/*---------------------------------------------------------------------------------------------------------------
Log & Version

Versienummer    Datum         Naam            Mutatie
---------------------------------------------------------------------------------------------------------------
0.1.0           2026-07-17    Alice           feat: nieuw dashboard Sales
                                              fix: correcte omzet-KPI
0.0.9           2026-07-10    Bob             vorige wijziging
---------------------------------------------------------------------------------------------------------------*/
```

Bestaande regels blijven bewaard onder de nieuwe entry. Het bestand wordt gevonden
via `load_script.path` → glob → `///$tab ...Changelog` header. Wordt er geen
`.qvs` gevonden, dan komt het blok in `qlik_changelog_block.txt`.

## Optionele AI-polish

Zonder `GEMINI_API_KEY` is alles deterministisch en is geen secret nodig. Is de key
aanwezig, dan herformuleert Gemini **alleen de tekst** van de release-notes en de
mutatieomschrijvingen. Het Qlik-blok wordt daarna hervalideerd; bij twijfel valt het
systeem terug op het deterministische blok. AI kan het laadscript dus nooit breken.

## Architectuur

```
scripts/
├── qlik_release.py      # release-flow op dev -> main (entrypoint)
├── qlik_preview.py      # changelog-preview op feature -> dev (entrypoint)
└── core/                # portable, platform-agnostisch
    ├── config.py        # laadt qlik-release.yml + defaults
    ├── semver.py        # rolling-digit carry
    ├── gitutil.py       # git-wrappers (commits, identiteit)
    ├── changelog.py     # CHANGELOG.md bouwen/mergen
    ├── qlik_block.py    # Qlik-blok bouwen/injecteren/valideren
    ├── notes.py         # release-notes body
    ├── gemini.py        # optionele AI-polish (no-op zonder key)
    ├── platform.py      # platformdetectie + abstracte adapter
    ├── platform_github.py
    └── platform_gitlab.py
.github/workflows/       # dunne GitHub callers + reusable workflows
.gitlab-ci.yml           # GitLab template (via include)
.github/scripts/init_repo.py  # seedt nieuwe repo's (workflows, config, dev, protection)
```

Qlik/Gitoqlok-specifieke aannames zitten achter `core/qlik_block.py` en de config;
platformverschillen achter `core/platform_*.py`.

## FAQ

**Heb ik een Gemini API-key nodig?** Nee. Zonder key werkt alles deterministisch.
Een key voegt alleen tekstuele polish toe.

**De pipeline vindt mijn Qlik-scriptbestand niet.** Zet `load_script.path` in
`qlik-release.yml`, of zorg dat het bestand `Changelog.qvs` heet of een
`///$tab ...Changelog` header heeft.

**Mag CI de app zelf bijwerken?** Nee — CI wijzigt alleen het bestand. De app
bijwerken doe je via een Gitoqlok pull. Zie [ADR-0001](docs/adr/0001-gitoqlok-writeback-boundary.md).

**Retriggert de terugcommit de pipeline?** Nee. Release-commits krijgen de marker
`[skip release]` en een bot-auteur; het script en de caller-workflow slaan die over.

**Welke commits veroorzaken géén release?** (1) commits met `[skip release]` in het
bericht — inclusief de seeding van de workflow-bestanden; (2) commits door de
release-bot; (3) commits waarvan het bericht een patroon uit `skip_release_when`
bevat. Standaard staan daar Gitoqlok-housekeeping-commits in
(`Gitoqlok: auto-restore app properties after merge` en `Update branches table`);
je kunt eigen patronen toevoegen in `qlik-release.yml`. Zo veroorzaakt het
plaatsen van de workflow-bestanden zelf geen release.

**Ik wil minor/major forceren.** Maak handmatig een tag aan (bijv. `v0.2.0`); de
volgende release rekent vanaf daar verder.
