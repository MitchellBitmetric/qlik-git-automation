"""
gitlab_init.py – Seedt Gitoqlok-beheerde Qlik-projecten (GitLab)
================================================================
GitLab-tegenhanger van .github/scripts/init_repo.py. Loopt een group af en
seedt elk project met '%gitoqlok_repo%' in de beschrijving: de include-based
.gitlab-ci.yml, het configbestand, de dev-branch en branch/tag-protection.
Idempotent — bestaande bestanden/branches worden overgeslagen.

Bedoeld voor een geplande group-pipeline (zero-touch onboarding).

Env:
  GITLAB_API_TOKEN  PAT (api + write_repository) op group-niveau
  GROUP_ID          numeriek group-id of pad (bijv. 'bitmetric-bv')
  CI_API_V4_URL     optioneel (default https://gitlab.com/api/v4)
  AUTOMATION_PROJECT_PATH  optioneel (default bitmetric-bv/qlik-git-automation)
"""

import os
from urllib.parse import quote

import requests

TOKEN     = os.environ["GITLAB_API_TOKEN"]
GROUP_ID  = os.environ["GROUP_ID"]
API       = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
AUTOMATION = os.environ.get("AUTOMATION_PROJECT_PATH", "bitmetric-bv/qlik-git-automation")

HEADERS = {"PRIVATE-TOKEN": TOKEN}
QLIK_MARKER = "%gitoqlok_repo%"

CI_FILE_PATH = ".gitlab-ci.yml"
CI_FILE_CONTENT = f"""\
# Qlik Git Automation — release + changelog via gedeelde template.
include:
  - project: '{AUTOMATION}'
    file: '/.gitlab-ci.yml'
    ref: main
"""

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

SEEDED_SENTINEL = CI_FILE_PATH


# ──────────────────────────────────────────────
# API-helpers
# ──────────────────────────────────────────────

def list_group_projects() -> list[dict]:
    projects: list[dict] = []
    page = 1
    while True:
        url = (
            f"{API}/groups/{quote(str(GROUP_ID), safe='')}/projects"
            f"?include_subgroups=true&per_page=100&page={page}&archived=false"
        )
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        projects.extend(batch)
        page += 1
    return projects


def file_exists(pid: int, path: str, branch: str) -> bool:
    url = f"{API}/projects/{pid}/repository/files/{quote(path, safe='')}?ref={branch}"
    return requests.get(url, headers=HEADERS, timeout=30).status_code == 200


def push_file(pid: int, path: str, content: str, branch: str) -> None:
    if file_exists(pid, path, branch):
        print(f"    ⚠ {path} bestaat al — overgeslagen.")
        return
    url  = f"{API}/projects/{pid}/repository/files/{quote(path, safe='')}"
    body = {
        "branch": branch,
        "content": content,
        "commit_message": "chore: workflow-bestanden toegevoegd via qlik-git-automation [skip release]",
    }
    resp = requests.post(url, headers=HEADERS, json=body, timeout=30)
    if resp.status_code in (200, 201):
        print(f"    ✔ {path} aangemaakt")
    else:
        print(f"    ✘ Fout bij {path}: {resp.status_code} – {resp.text}")
        resp.raise_for_status()


def ensure_dev_branch(pid: int, default_branch: str) -> None:
    if file_exists_branch(pid, "dev"):
        print("    ⚠ dev-branch bestaat al — overgeslagen.")
        return
    url = f"{API}/projects/{pid}/repository/branches?branch=dev&ref={default_branch}"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code == 201:
        print("    ✔ dev-branch aangemaakt")
    else:
        print(f"    ⚠ dev-branch niet aangemaakt: {resp.status_code} – {resp.text}")


def file_exists_branch(pid: int, branch: str) -> bool:
    url = f"{API}/projects/{pid}/repository/branches/{quote(branch, safe='')}"
    return requests.get(url, headers=HEADERS, timeout=30).status_code == 200


def protect_main(pid: int, branch: str) -> None:
    """main: geen directe push, alleen merge door maintainers. Best-effort."""
    # Bestaande protection eerst verwijderen om conflicten te vermijden.
    requests.delete(
        f"{API}/projects/{pid}/protected_branches/{quote(branch, safe='')}",
        headers=HEADERS, timeout=30,
    )
    url = (
        f"{API}/projects/{pid}/protected_branches"
        f"?name={quote(branch, safe='')}&push_access_level=0&merge_access_level=40"
    )
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code in (200, 201):
        print(f"    ✔ Branch protection op '{branch}' ingesteld")
    else:
        print(f"    ⚠ Branch protection niet ingesteld: {resp.status_code} – {resp.text}")


def protect_tags(pid: int) -> None:
    url = f"{API}/projects/{pid}/protected_tags?name=v*&create_access_level=40"
    resp = requests.post(url, headers=HEADERS, timeout=30)
    if resp.status_code in (200, 201):
        print("    ✔ Protected tag 'v*' ingesteld")
    elif resp.status_code == 409:
        print("    ⚠ Protected tag 'v*' bestaat al — overgeslagen.")
    else:
        print(f"    ⚠ Protected tag niet ingesteld: {resp.status_code} – {resp.text}")


# ──────────────────────────────────────────────
# Seed één project + scan
# ──────────────────────────────────────────────

def seed_project(project: dict) -> bool:
    pid  = project["id"]
    path = project.get("path_with_namespace", str(pid))
    branch = project.get("default_branch") or "main"

    print(f"  ▶ {path}  (default: {branch})")
    push_file(pid, CI_FILE_PATH, CI_FILE_CONTENT, branch)
    push_file(pid, CONFIG_FILE_PATH, CONFIG_FILE_CONTENT, branch)
    ensure_dev_branch(pid, branch)
    protect_main(pid, branch)
    protect_tags(pid)
    return True


def scan_group() -> None:
    print(f"── Scan group '{GROUP_ID}' op Qlik-projecten ──")
    projects = list_group_projects()
    print(f"  {len(projects)} project(en) gevonden")

    seeded = skipped = 0
    for project in projects:
        description = project.get("description") or ""
        if QLIK_MARKER not in description:
            continue
        branch = project.get("default_branch") or "main"
        if file_exists(project["id"], SEEDED_SENTINEL, branch):
            print(f"  ⏭  {project.get('path_with_namespace')} al geseed — overgeslagen")
            skipped += 1
            continue
        if seed_project(project):
            seeded += 1

    print(f"\n✅ Scan klaar — {seeded} geseed, {skipped} al gereed.")


if __name__ == "__main__":
    scan_group()
