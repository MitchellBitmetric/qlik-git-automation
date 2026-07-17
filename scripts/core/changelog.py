"""changelog.py – deterministische changelog uit git-commits.

Bouwt een Keep-a-Changelog entry op basis van de commits die sinds de laatste
tag zijn samengevoegd. Conventional-Commit prefixes worden gegroepeerd; commits
zonder herkenbaar prefix komen onder 'Overig'.

Herbruikt de merge-logica (update_changelog) uit het oorspronkelijke
pr_automation.py, zodat een herhaalde run dezelfde versie-entry vervangt in
plaats van dupliceert (idempotent).
"""

from __future__ import annotations

import re

from .gitutil import Commit

CHANGELOG_HEADER = (
    "# Changelog\n\n"
    "Alle wijzigingen aan dit project worden hier bijgehouden.\n\n"
)

# Conventional-Commit prefix -> Keep a Changelog kop
_TYPE_MAP = {
    "feat": "Added",
    "fix": "Fixed",
    "perf": "Changed",
    "refactor": "Changed",
    "revert": "Removed",
    "docs": "Documentation",
    "style": "Changed",
    "test": "Changed",
    "build": "Changed",
    "ci": "Changed",
    "chore": "Changed",
}
_GROUP_ORDER = ["Added", "Changed", "Fixed", "Removed", "Documentation", "Overig"]

_CC_RE = re.compile(r"^(?P<type>\w+)(?:\([^)]*\))?(?P<bang>!)?:\s*(?P<desc>.+)$")


def classify_commit(subject: str) -> tuple[str, str]:
    """Geef (kop, beschrijving) voor één commit-onderwerp."""
    m = _CC_RE.match(subject)
    if not m:
        return "Overig", subject
    ctype = m.group("type").lower()
    heading = _TYPE_MAP.get(ctype, "Overig")
    return heading, m.group("desc").strip()


def group_commits(commits: list[Commit]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for c in commits:
        heading, desc = classify_commit(c.subject)
        groups.setdefault(heading, []).append(desc)
    return groups


def build_changelog_entry(version: str, date: str, commits: list[Commit]) -> str:
    """Markdown-entry voor CHANGELOG.md (heading + gegroepeerde bullets)."""
    lines = [f"## [{version}] - {date}", ""]
    if not commits:
        lines.append("- Geen noemenswaardige wijzigingen.")
        return "\n".join(lines) + "\n"

    groups = group_commits(commits)
    for heading in _GROUP_ORDER:
        items = groups.get(heading)
        if not items:
            continue
        lines.append(f"### {heading}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_changelog(current: str, new_entry: str) -> str:
    """Voeg entry toe of vervang de bestaande entry met hetzelfde versienummer.

    Overgenomen uit het oorspronkelijke pr_automation.py; houdt de operatie
    idempotent bij een herhaalde run op dezelfde versie.
    """
    version_match = re.search(r"^## \[?(v[\d.]+)\]?", new_entry, re.MULTILINE)

    if version_match and current:
        version = re.escape(version_match.group(1))
        existing = re.search(
            rf"^## \[?{version}\]?.*?(?=^## |\Z)",
            current, re.MULTILINE | re.DOTALL
        )
        if existing:
            updated = current[:existing.start()] + new_entry + "\n\n" + current[existing.end():]
            return updated.rstrip() + "\n"

    if not current:
        return CHANGELOG_HEADER + new_entry + "\n"
    if current.startswith("# "):
        lines = current.split("\n")
        insert = 1
        while insert < len(lines) and lines[insert].strip() == "":
            insert += 1
        lines.insert(insert, new_entry + "\n")
        return "\n".join(lines)
    return new_entry + "\n\n" + current
