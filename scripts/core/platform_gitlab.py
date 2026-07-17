"""platform_gitlab.py – GitLab-adapter.

Spiegelt de GitHub-adapter: identiek gedrag, alleen de API- en push-details
verschillen. Auth via GITLAB_API_TOKEN (PAT met api + write_repository).
"""

from __future__ import annotations

import os
import subprocess
from urllib.parse import urlparse

import requests


class GitLabPlatform:
    name = "gitlab"

    def __init__(self) -> None:
        self.token = os.environ.get("GITLAB_API_TOKEN") or os.environ.get("CI_JOB_TOKEN", "")
        self.api = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
        self.project_id = os.environ["CI_PROJECT_ID"]
        self._repo = os.environ.get("CI_PROJECT_PATH", "")
        self.server_url = os.environ.get("CI_SERVER_URL", "https://gitlab.com")
        self.headers = {"PRIVATE-TOKEN": self.token}

    @property
    def repo_slug(self) -> str:
        return self._repo

    def _authenticated_remote(self) -> str:
        host = urlparse(self.server_url).netloc
        return f"https://oauth2:{self.token}@{host}/{self._repo}.git"

    def create_tag_push(self, tag: str) -> None:
        subprocess.run(["git", "tag", "-a", tag, "-m", f"Release {tag}"], check=True)
        subprocess.run(["git", "push", self._authenticated_remote(), tag], check=True)
        print(f"  ✔ Git-tag '{tag}' aangemaakt en gepusht")

    def push_commit(self, branch: str) -> None:
        subprocess.run(["git", "push", self._authenticated_remote(), f"HEAD:{branch}"], check=True)
        print(f"  ✔ Commit gepusht naar {branch}")

    def create_release(self, tag: str, name: str, body: str, commit_sha: str) -> str:
        url = f"{self.api}/projects/{self.project_id}/releases"
        payload = {"tag_name": tag, "name": name, "description": body, "ref": commit_sha}
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        if resp.status_code in (200, 201):
            release_url = f"{self.server_url}/{self._repo}/-/releases/{tag}"
            print(f"  ✔ GitLab Release aangemaakt: {release_url}")
            return release_url
        print(f"  ✘ Fout bij aanmaken release: {resp.status_code} – {resp.text}")
        resp.raise_for_status()
        return ""
