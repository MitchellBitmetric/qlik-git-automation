# Onboarding — nieuwe Qlik-repo met minimaal handwerk

Doel: een nieuwe Gitoqlok-repo werkt **zonder bestanden te kopiëren en zonder
per-repo secrets**. Je zet twee dingen één keer op org/group-niveau in; daarna
is aanmaken van een repo genoeg.

## Waar staat de automation-repo? (topologie)

De plek van `qlik-git-automation` (**AUTOMATION_ORG**) staat los van de org(s) met
de Qlik-repo's (**TARGET_ORGS**). Kies je model:

| Model | Wanneer | AUTOMATION_ORG | TARGET_ORGS | Zichtbaarheid automation-repo |
|-------|---------|----------------|-------------|-------------------------------|
| **A — centraal** | eigen org(s) binnen één GitHub **Enterprise** | `bitmetric-bv` | `orgA,orgB,…` | **public** óf private mét Enterprise-sharing aan |
| **B — per org** | losstaande (klant-)orgs | die org zelf | die org zelf | private mag; alles blijft binnen de org |

> **Waarom de zichtbaarheid ertoe doet:** een *private* reusable workflow in org A
> kan niet cross-org worden aangeroepen vanuit org B, tenzij beide in dezelfde
> Enterprise zitten met workflow-sharing aan. Voor model A moet de automation-repo
> dus **public** zijn óf de Enterprise-sharing aanstaan. Model B omzeilt dit door
> een kopie per org (zie [sync](#model-b--kopie-per-org-bijwerken)).

Je stelt AUTOMATION_ORG / TARGET_ORGS in als **repo-variabelen** op de
automation-repo (`Settings → Secrets and variables → Actions → Variables`), of als
input bij een handmatige scan-run. Zonder instelling gelden ze als de eigen org
(= model B).

## Eenmalig (per organisatie / group)

### 1. Secrets op org/group-niveau
Zo hoef je nooit per repo een key in te stellen.

**GitHub** — op de **automation-repo** → **Settings → Secrets and variables → Actions**:
| Secret | Waarde |
|--------|--------|
| `AUTOMATION_PAT` | PAT met toegang tot **elke TARGET_ORG** (contents + workflows + administration). Model A: één token dat alle doel-orgs kan bereiken (binnen de Enterprise). Model B: het org-eigen token. |
| `GEMINI_API_KEY` | optioneel, voor AI-polish |

En als **Variables** (zelfde scherm, tab *Variables*), alleen voor model A nodig:
| Variable | Waarde |
|----------|--------|
| `AUTOMATION_ORG` | `bitmetric-bv` (waar de automation-repo staat) |
| `TARGET_ORGS` | `orgA,orgB` (komma-gescheiden org(s) om te scannen) |

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

## Model B — kopie per org bijwerken

Bij losstaande orgs host je een kopie van `qlik-git-automation` in elke org.
Updates uitrollen kan zonder handwerk via een van deze routes:

- **Fork + "Sync fork":** fork de canonieke repo naar elke org; werk bij met de
  GitHub "Sync fork"-knop of `gh repo sync <org>/qlik-git-automation`.
- **Mirror push:** een workflow in de canonieke repo die bij elke release naar de
  kopieën pusht (vereist een PAT met toegang tot die orgs).

Omdat consumers naar `@main` van hún org-kopie verwijzen, krijgen ze de update
zodra de kopie is bijgewerkt — zonder iets in de Qlik-repo's te wijzigen.

## Afwijken van de defaults
Alleen nodig als een repo iets anders wil (ander scriptpad, andere tab-marker,
andere startversie): pas `qlik-release.yml` in die repo aan. Zie
[qlik-release.example.yml](../qlik-release.example.yml). Zonder dit bestand gelden
de defaults.
