# Onboarding — nieuwe Qlik-repo met minimaal handwerk

Doel: een nieuwe Gitoqlok-repo werkt **zonder bestanden te kopiëren en zonder
per-repo secrets**. Je zet twee dingen één keer op org/group-niveau in; daarna
is aanmaken van een repo genoeg.

## Eenmalig (per organisatie / group)

### 1. Secrets op org/group-niveau
Zo hoef je nooit per repo een key in te stellen.

**GitHub** — Org → **Settings → Secrets and variables → Actions**:
| Secret | Waarde | Scope |
|--------|--------|-------|
| `AUTOMATION_PAT` | PAT met `repo` + `admin:org` (voor seeden/branch protection) | automation-repo (of org) |
| `GEMINI_API_KEY` | optioneel, voor AI-polish | All repositories |

**GitLab** — Group → **Settings → CI/CD → Variables**:
| Variable | Waarde |
|----------|--------|
| `GITLAB_API_TOKEN` | group-PAT met `api` + `write_repository` |
| `GEMINI_API_KEY` | optioneel |

### 2. De geplande scan aanzetten
De scan seedt automatisch elke repo/project met de marker (zie onder).

**GitHub** — al geregeld: [scheduled-init.yml](../.github/workflows/scheduled-init.yml)
draait elk uur in de automation-repo. Handmatig starten kan via **Actions → Scheduled
Repo Onboarding → Run workflow**. Vereist alleen `AUTOMATION_PAT`.

**GitLab** — maak in de automation-project een schedule aan:
**Settings → CI/CD → Pipeline schedules → New schedule**, bijv. elk uur, met
variabele `GROUP_ID` (group-pad of -id). De job [`qlik_onboard_scan`](../.gitlab-ci.yml)
draait dan `scripts/gitlab_init.py`.

## Per nieuwe repo — dit is alles

1. Maak de repo/project aan.
2. Zet **`%gitoqlok_repo%`** in de **beschrijving** van de repo.
3. Klaar. Binnen een uur (of direct na een handmatige scan-run) seedt de
   automatisering: caller-workflow(s)/`.gitlab-ci.yml`, `qlik-release.yml`,
   de `dev`-branch en branch/tag-protection.

> De scan is **idempotent**: al geseede repo's worden overgeslagen (herkend aan
> de aanwezige release-workflow / `.gitlab-ci.yml`). Handmatig hersturen kan geen
> kwaad.

## Wil je het direct (0 vertraging) i.p.v. per uur?

- **GitHub:** draai de scan handmatig (**Run workflow**), of laat een
  organization-webhook op "Repository → created" een `repository_dispatch`
  `[repo-created]` naar de automation-repo sturen — dan seedt
  [init-new-repo.yml](../.github/workflows/init-new-repo.yml) meteen die ene repo.
- **GitLab:** draai de schedule handmatig (**Play**), of trigger de pipeline via
  een group-webhook.

## Afwijken van de defaults
Alleen nodig als een repo iets anders wil (ander scriptpad, andere tab-marker,
andere startversie): pas `qlik-release.yml` in die repo aan. Zie
[qlik-release.example.yml](../qlik-release.example.yml). Zonder dit bestand gelden
de defaults.
