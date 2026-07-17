"""platform.py – abstractie over de CI-platforms.

Alles behalve (a) het lezen van PR/MR-metadata en (b) het aanmaken van een
release is puur git + bestands-IO en zit in de andere core-modules. Deze module
detecteert het platform en levert de juiste adapter.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class Platform(ABC):
    name: str

    @property
    @abstractmethod
    def repo_slug(self) -> str:
        """bijv. 'org/repo' (GitHub) of 'group/project' (GitLab)."""

    @abstractmethod
    def create_release(self, tag: str, name: str, body: str, commit_sha: str) -> str:
        """Maak een release aan; geef de URL terug."""

    @abstractmethod
    def create_tag_push(self, tag: str) -> None:
        """Maak een geannoteerde tag en push die naar origin."""

    @abstractmethod
    def push_commit(self, branch: str) -> None:
        """Push de huidige HEAD naar ``branch`` op origin."""


def detect_platform() -> Platform:
    """Kies de adapter op basis van de CI-omgevingsvariabelen."""
    if os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("GITHUB_REPOSITORY"):
        from .platform_github import GitHubPlatform
        return GitHubPlatform()
    if os.environ.get("GITLAB_CI") == "true" or os.environ.get("CI_PROJECT_ID"):
        from .platform_gitlab import GitLabPlatform
        return GitLabPlatform()
    raise RuntimeError(
        "Kon het CI-platform niet bepalen. Zet GITHUB_ACTIONS/GITHUB_REPOSITORY "
        "of GITLAB_CI/CI_PROJECT_ID."
    )
