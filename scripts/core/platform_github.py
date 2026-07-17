"""platform_github.py – GitHub-adapter.

Herbruikt create_github_release uit het oorspronkelijke create_release.py.
"""

from __future__ import annotations

import os
import subprocess

import requests

GH_API = "https://api.github.com"


class GitHubPlatform:
    name = "github"

    def __init__(self) -> None:
        self.token = os.environ["GITHUB_TOKEN"]
        self._repo = os.environ.get("GITHUB_REPOSITORY") or os.environ["REPO_FULL_NAME"]
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    @property
    def repo_slug(self) -> str:
        return self._repo

    def create_tag_push(self, tag: str) -> None:
        subprocess.run(["git", "tag", "-a", tag, "-m", f"Release {tag}"], check=True)
        subprocess.run(["git", "push", "origin", tag], check=True)
        print(f"  ✔ Git-tag '{tag}' aangemaakt en gepusht")

    def push_commit(self, branch: str) -> None:
        subprocess.run(["git", "push", "origin", f"HEAD:{branch}"], check=True)
        print(f"  ✔ Commit gepusht naar {branch}")

    def create_release(self, tag: str, name: str, body: str, commit_sha: str) -> str:
        url = f"{GH_API}/repos/{self._repo}/releases"
        payload = {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False,
            "target_commitish": commit_sha,
        }
        resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
        if resp.status_code == 201:
            release_url = resp.json().get("html_url", "")
            print(f"  ✔ GitHub Release aangemaakt: {release_url}")
            return release_url
        print(f"  ✘ Fout bij aanmaken release: {resp.status_code} – {resp.text}")
        resp.raise_for_status()
        return ""
