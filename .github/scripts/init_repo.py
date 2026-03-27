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
name: PR Changelog & Docs Automation

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches:
      - main
      - master

jobs:
  run-automation:
    uses: {org}/qlik-git-automation/.github/workflows/pr-changelog.yml@main
    secrets: inherit
""",
    ".github/workflows/create-release.yml": """\
name: Create Release

on:
  push:
    branches:
      - main
      - master

jobs:
  create-release:
    if: ${{{{ !contains(github.event.head_commit.message, 'automatisch changelog') }}}}
    uses: {org}/qlik-git-automation/.github/workflows/create-release.yml@main
    secrets: inherit
"""
}


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

    print("\n✅ Klaar!")


if __name__ == "__main__":
    main()