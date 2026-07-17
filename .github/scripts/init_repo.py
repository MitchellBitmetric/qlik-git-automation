"""
init_repo.py – Seedt Gitoqlok-beheerde Qlik-repo's (GitHub)
============================================================
Plaatst automatisch de dunne caller-workflows, het configbestand, de
dev-branch en branch protection in een repo waarvan de beschrijving de marker
'%gitoqlok_repo%' bevat.

Twee modi (idempotent — bestaande bestanden/branches worden overgeslagen):
  • single : seed één repo (REPO_NAME gezet) — bijv. via repository_dispatch.
  • scan   : loop de hele org af en seed elke repo met de marker (geen
             REPO_NAME) — bedoeld voor een geplande run (zero-touch onboarding).
"""

import os
import base64
import requests

GH_TOKEN  = os.environ["GH_TOKEN"]
ORG_NAME  = os.environ["ORG_NAME"]
REPO_NAME = os.environ.get("REPO_NAME")  # leeg = scan-modus

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
}

API = "https://api.github.com"

QLIK_MARKER = "%gitoqlok_repo%"

WORKFLOWS = {
    ".github/workflows/pr-changelog.yml": """\
name: Qlik Changelog Preview

# Draait op PR's naar de integratiebranch (feature/* -> dev).
on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches:
      - dev

jobs:
  preview:
    uses: {org}/qlik-git-automation/.github/workflows/pr-changelog.yml@main
    secrets: inherit
""",
    ".github/workflows/release.yml": """\
name: Qlik Release

# Draait op merge dev -> main. Loop-beveiliging zit in het release-script,
# maar we slaan een expliciete release-commit hier al over.
on:
  push:
    branches:
      - main

jobs:
  release:
    if: ${{{{ !contains(github.event.head_commit.message, '[skip release]') }}}}
    uses: {org}/qlik-git-automation/.github/workflows/release.yml@main
    secrets: inherit
""",
}

# Configbestand dat we in nieuwe repo's plaatsen (minimale near-zero setup).
CONFIG_FILE_PATH = "qlik-release.yml"
CONFIG_FILE_CONTENT = """\
# qlik-release.yml — zie qlik-git-automation voor alle opties.
main_branch: main
dev_branch: dev
load_script:
  path: ""
  glob:
    - "**/Changelog.qvs"
    - "**/*changelog*.qvs"
  tab_marker: "Changelog"
initial_version: "v0.0.1"
ai:
  polish:
    - release_notes
    - qlik_block
"""

# Bestand dat als "al geseed"-markering geldt (idempotente scan).
SEEDED_SENTINEL = ".github/workflows/release.yml"


# ──────────────────────────────────────────────
# API-helpers (repo als parameter → herbruikbaar in scan-modus)
# ──────────────────────────────────────────────

def get_repo_info(repo: str) -> dict:
    resp = requests.get(f"{API}/repos/{ORG_NAME}/{repo}", headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def file_exists(repo: str, path: str, branch: str) -> bool:
    url = f"{API}/repos/{ORG_NAME}/{repo}/contents/{path}?ref={branch}"
    return requests.get(url, headers=HEADERS, timeout=30).status_code == 200


def push_file(repo: str, path: str, content: str, branch: str) -> None:
    if file_exists(repo, path, branch):
        print(f"    ⚠ {path} bestaat al — overgeslagen.")
        return
    url     = f"{API}/repos/{ORG_NAME}/{repo}/contents/{path}"
    encoded = base64.b64encode(content.encode()).decode()
    body    = {
        "message": "chore: workflow-bestanden toegevoegd via qlik-git-automation",
        "content": encoded,
        "branch":  branch,
    }
    resp = requests.put(url, headers=HEADERS, json=body, timeout=30)
    if resp.status_code == 201:
        print(f"    ✔ {path} aangemaakt")
    else:
        print(f"    ✘ Fout bij {path}: {resp.status_code} – {resp.text}")
        resp.raise_for_status()


def get_branch_sha(repo: str, branch: str) -> str | None:
    url  = f"{API}/repos/{ORG_NAME}/{repo}/git/ref/heads/{branch}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    return resp.json()["object"]["sha"] if resp.status_code == 200 else None


def ensure_dev_branch(repo: str, default_branch: str) -> None:
    url = f"{API}/repos/{ORG_NAME}/{repo}/git/ref/heads/dev"
    if requests.get(url, headers=HEADERS, timeout=30).status_code == 200:
        print("    ⚠ dev-branch bestaat al — overgeslagen.")
        return
    sha = get_branch_sha(repo, default_branch)
    if not sha:
        print("    ⚠ Kon SHA van default branch niet ophalen — dev-branch niet aangemaakt.")
        return
    resp = requests.post(
        f"{API}/repos/{ORG_NAME}/{repo}/git/refs",
        headers=HEADERS, json={"ref": "refs/heads/dev", "sha": sha}, timeout=30,
    )
    if resp.status_code == 201:
        print("    ✔ dev-branch aangemaakt")
    else:
        print(f"    ⚠ dev-branch niet aangemaakt: {resp.status_code} – {resp.text}")


def protect_main(repo: str, branch: str) -> None:
    """Beperk main tot PR-merges (releases). Best-effort; vereist admin-rechten."""
    url = f"{API}/repos/{ORG_NAME}/{repo}/branches/{branch}/protection"
    body = {
        "required_status_checks": None,
        "enforce_admins": False,
        "required_pull_request_reviews": {"required_approving_review_count": 1},
        "restrictions": None,
        "allow_force_pushes": False,
        "allow_deletions": False,
    }
    resp = requests.put(url, headers=HEADERS, json=body, timeout=30)
    if resp.status_code == 200:
        print(f"    ✔ Branch protection op '{branch}' ingesteld")
    else:
        print(f"    ⚠ Branch protection niet ingesteld: {resp.status_code} – {resp.text}")


# ──────────────────────────────────────────────
# Seed één repo
# ──────────────────────────────────────────────

def seed_repo(repo: str, info: dict | None = None) -> bool:
    """Seed één repo. Geeft True als er iets is gedaan, False bij overslaan."""
    info        = info or get_repo_info(repo)
    description = info.get("description") or ""
    branch      = info.get("default_branch", "main")

    if QLIK_MARKER not in description:
        return False

    print(f"  ▶ {ORG_NAME}/{repo}  (default: {branch})")

    for path, content in WORKFLOWS.items():
        push_file(repo, path, content.format(org=ORG_NAME), branch)
    push_file(repo, CONFIG_FILE_PATH, CONFIG_FILE_CONTENT, branch)

    ensure_dev_branch(repo, branch)
    protect_main(repo, branch)
    return True


# ──────────────────────────────────────────────
# Scan de hele org
# ──────────────────────────────────────────────

def list_org_repos() -> list[dict]:
    repos: list[dict] = []
    page = 1
    while True:
        url = f"{API}/orgs/{ORG_NAME}/repos?per_page=100&page={page}&type=all"
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def scan_org() -> None:
    print(f"── Scan org '{ORG_NAME}' op Qlik-repo's ──")
    repos = list_org_repos()
    print(f"  {len(repos)} repo(s) gevonden")

    seeded = skipped = 0
    for info in repos:
        repo = info["name"]
        description = info.get("description") or ""
        if QLIK_MARKER not in description:
            continue
        branch = info.get("default_branch", "main")
        if file_exists(repo, SEEDED_SENTINEL, branch):
            print(f"  ⏭  {repo} al geseed — overgeslagen")
            skipped += 1
            continue
        if seed_repo(repo, info):
            seeded += 1

    print(f"\n✅ Scan klaar — {seeded} geseed, {skipped} al gereed.")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    if REPO_NAME:
        print(f"── Repo initialiseren: {ORG_NAME}/{REPO_NAME} ──")
        if not seed_repo(REPO_NAME):
            print(f"  ⚠ Geen Qlik Sense repo (marker '{QLIK_MARKER}' niet gevonden) — overgeslagen.")
        else:
            print("\n✅ Klaar!")
    else:
        scan_org()


if __name__ == "__main__":
    main()
