# Branchmodel & branch protection

Het aanbevolen branchmodel voor Gitoqlok-beheerde Qlik-repo's:

| Branch | Doel | Wie schrijft |
|--------|------|--------------|
| `main` | **beschermd** — alleen releases | uitsluitend via PR/MR merge vanaf `dev` |
| `dev`  | integratie | PR/MR merge vanaf `feature/*` |
| `feature/*` | losse wijzigingen | committer via Gitoqlok |

`init_repo.py` maakt bij seeding automatisch de `dev`-branch aan en zet
best-effort branch protection op `main`. Onderstaande instellingen kun je
handmatig controleren/aanvullen (branch protection kan niet volledig vanuit
repo-bestanden worden afgedwongen).

## GitHub

**Settings → Branches → Add branch ruleset** (of Branch protection rule) voor `main`:

- ☑️ Require a pull request before merging (min. 1 approval)
- ☑️ Block force pushes
- ☑️ Restrict deletions
- ☐ (optioneel) Require status checks: de "Qlik Release" workflow

Voor `dev`: geen strikte bescherming nodig; eventueel PR-verplichting.

## GitLab

**Settings → Repository → Protected branches**:

| Branch | Allowed to merge | Allowed to push |
|--------|------------------|-----------------|
| `main` | Maintainers | No one (alleen via MR) |
| `dev`  | Developers + Maintainers | Developers + Maintainers |

**Settings → Repository → Protected tags**: patroon `v*` → Maintainers + CI/CD,
zodat de release-job tags mag pushen.

**Settings → CI/CD → Variables**: `GITLAB_API_TOKEN` (PAT met `api` +
`write_repository`), en optioneel `GEMINI_API_KEY`. Zet ze op *Protected* als de
branches protected zijn.
