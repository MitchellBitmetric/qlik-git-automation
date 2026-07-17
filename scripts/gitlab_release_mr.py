"""gitlab_release_mr.py – maakt/bijwerkt de dev -> main MR (GitLab).

GitLab-tegenhanger van qlik_release_pr.py: draait op elke push naar dev en zet
op de dev -> main merge request een automatisch berekende titel ("Release
vX.Y.Z") en changelog-omschrijving via de GitLab MR-API. Maakt GEEN tag/release.

Env:
  GITLAB_API_TOKEN  PAT (api) — zelfde secret als de rest van de CI
  CI_PROJECT_ID     numeriek project-id (door GitLab gezet)
  CI_API_V4_URL     optioneel (default https://gitlab.com/api/v4)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

from core.config import load_config
from core.release_pr import build_release_pr_text
from qlik_release import BOT_NAME, SKIP_MARKER

TOKEN = os.environ["GITLAB_API_TOKEN"]
PROJECT_ID = os.environ["CI_PROJECT_ID"]
API = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
HEADERS = {"PRIVATE-TOKEN": TOKEN}


def _find_open_mr(source: str, target: str) -> int | None:
    resp = requests.get(
        f"{API}/projects/{PROJECT_ID}/merge_requests",
        headers=HEADERS,
        params={"state": "opened", "source_branch": source, "target_branch": target},
        timeout=30,
    )
    resp.raise_for_status()
    items = resp.json()
    return items[0]["iid"] if items else None


def main() -> int:
    print("── Dev -> main MR voorbereiden (GitLab) ──")

    config = load_config()
    main_branch = config["main_branch"]
    dev_branch = config["dev_branch"]

    _, title, body = build_release_pr_text(config, BOT_NAME, SKIP_MARKER)

    iid = _find_open_mr(dev_branch, main_branch)
    if iid:
        resp = requests.put(
            f"{API}/projects/{PROJECT_ID}/merge_requests/{iid}",
            headers=HEADERS,
            json={"title": title, "description": body},
            timeout=30,
        )
        resp.raise_for_status()
        print(f"  ✔ MR !{iid} bijgewerkt: {title}")
        return 0

    resp = requests.post(
        f"{API}/projects/{PROJECT_ID}/merge_requests",
        headers=HEADERS,
        json={
            "source_branch": dev_branch,
            "target_branch": main_branch,
            "title": title,
            "description": body,
        },
        timeout=30,
    )
    if resp.status_code == 409:
        # Geen commits verschil tussen dev en main — niets te mergen.
        print("  ℹ Geen verschil tussen dev en main — geen MR aangemaakt.")
        return 0
    resp.raise_for_status()
    print(f"  ✔ Nieuwe dev -> main MR aangemaakt: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
