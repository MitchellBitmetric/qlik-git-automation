"""
init_repo.py – Plaatst workflow-bestanden in een nieuwe Qlik Sense repo
========================================================================
Wordt getriggerd wanneer een nieuwe repo wordt aangemaakt in de organisatie.
Controleert of de repo description '%gitoqlok_repo%' bevat en plaatst
automatisch de benodigde workflow-bestanden.
"""

import os
import base64
import requests

GH_TOKEN  = os.environ["GH_TOKEN"]
ORG_NAME  = os.environ["ORG_NAME"]
REPO_NAME = os.environ["REPO_NAME"]

HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json"
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
"""
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


def get_repo_info() -> dict:
    url  = f"{API}/repos/{ORG_NAME}/{REPO_NAME}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def file_exists(path: str, branch: str) -> bool:
    url  = f"{API}/repos/{ORG_NAME}/{REPO_NAME}/contents/{path}?ref={branch}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    return resp.status_code == 200


def push_file(path: str, content: str, branch: str) -> None:
    if file_exists(path, branch):
        print(f"  ⚠ {path} bestaat al — overgeslagen.")
        return

    url     = f"{API}/repos/{ORG_NAME}/{REPO_NAME}/contents/{path}"
    encoded = base64.b64encode(content.encode()).decode()
    body    = {
        "message": "chore: workflow-bestanden toegevoegd via qlik-git-automation",
        "content": encoded,
        "branch":  branch
    }
    resp = requests.put(url, headers=HEADERS, json=body, timeout=30)
    if resp.status_code == 201:
        print(f"  ✔ {path} aangemaakt")
    else:
        print(f"  ✘ Fout bij {path}: {resp.status_code} – {resp.text}")
        resp.raise_for_status()


def get_default_branch_sha(branch: str) -> str | None:
    url  = f"{API}/repos/{ORG_NAME}/{REPO_NAME}/git/ref/heads/{branch}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return resp.json()["object"]["sha"]
    return None


def ensure_dev_branch(default_branch: str) -> None:
    """Maak de dev-integratiebranch aan als die nog niet bestaat."""
    url = f"{API}/repos/{ORG_NAME}/{REPO_NAME}/git/ref/heads/dev"
    if requests.get(url, headers=HEADERS, timeout=30).status_code == 200:
        print("  ⚠ dev-branch bestaat al — overgeslagen.")
        return
    sha = get_default_branch_sha(default_branch)
    if not sha:
        print("  ⚠ Kon SHA van default branch niet ophalen — dev-branch niet aangemaakt.")
        return
    resp = requests.post(
        f"{API}/repos/{ORG_NAME}/{REPO_NAME}/git/refs",
        headers=HEADERS, json={"ref": "refs/heads/dev", "sha": sha}, timeout=30,
    )
    if resp.status_code == 201:
        print("  ✔ dev-branch aangemaakt")
    else:
        print(f"  ⚠ dev-branch niet aangemaakt: {resp.status_code} – {resp.text}")


def protect_main(branch: str) -> None:
    """Beperk main tot PR-merges (releases). Best-effort; vereist admin-rechten."""
    url = f"{API}/repos/{ORG_NAME}/{REPO_NAME}/branches/{branch}/protection"
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
        print(f"  ✔ Branch protection op '{branch}' ingesteld")
    else:
        print(f"  ⚠ Branch protection niet ingesteld: {resp.status_code} – {resp.text}")


def main() -> None:
    print(f"── Repo initialiseren: {ORG_NAME}/{REPO_NAME} ──")

    info        = get_repo_info()
    description = info.get("description", "")
    branch      = info.get("default_branch", "main")

    print(f"  Description: {description}")

    if QLIK_MARKER not in description:
        print(f"  ⚠ Geen Qlik Sense repo (marker '{QLIK_MARKER}' niet gevonden) — overgeslagen.")
        return

    print(f"  ✔ Qlik Sense repo herkend")
    print(f"  Default branch: {branch}")

    for path, content in WORKFLOWS.items():
        push_file(path, content.format(org=ORG_NAME), branch)

    push_file(CONFIG_FILE_PATH, CONFIG_FILE_CONTENT, branch)

    print("\n▶ Branchmodel opzetten …")
    ensure_dev_branch(branch)
    protect_main(branch)

    print("\n✅ Klaar!")


if __name__ == "__main__":
    main()