"""gitutil.py – dunne wrappers rond git die op beide platforms identiek zijn."""

from __future__ import annotations

import subprocess


def _run(args: list[str]) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=True)
    return result.stdout


class Commit:
    __slots__ = ("sha", "subject", "author")

    def __init__(self, sha: str, subject: str, author: str):
        self.sha = sha
        self.subject = subject
        self.author = author

    def __repr__(self) -> str:  # pragma: no cover - debug convenience
        return f"Commit({self.sha[:7]} {self.subject!r})"


def get_commits_since(ref: str | None, head: str = "HEAD") -> list[Commit]:
    """Commits (nieuwste eerst) tussen ``ref`` en ``head``, merges uitgesloten.

    Wanneer ``ref`` None is (nog geen tag) worden alle commits t/m ``head``
    teruggegeven. Elke commit levert sha, onderwerp (eerste regel) en auteur.
    """
    range_spec = f"{ref}..{head}" if ref else head
    fmt = "%H%x1f%s%x1f%an"
    out = _run(["log", range_spec, "--no-merges", f"--pretty=format:{fmt}"])
    commits: list[Commit] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, subject, author = parts
        commits.append(Commit(sha.strip(), subject.strip(), author.strip()))
    return commits


def head_commit_message() -> str:
    return _run(["log", "-1", "--pretty=%B"]).strip()


def head_commit_author() -> str:
    return _run(["log", "-1", "--pretty=%an"]).strip()


def configure_bot_identity(name: str, email: str) -> None:
    subprocess.run(["git", "config", "user.name", name], check=True)
    subprocess.run(["git", "config", "user.email", email], check=True)
