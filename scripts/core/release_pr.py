"""release_pr.py – bereken titel + omschrijving voor de dev -> main release-PR/MR.

Platform-onafhankelijk: dezelfde deterministische berekening voedt zowel de
GitHub- als de GitLab-flow. Maakt zelf geen PR/MR aan — levert alleen tekst.
"""

from __future__ import annotations

import datetime

from core import changelog as cl
from core import notes as notes_mod
from core import semver
from core.gitutil import get_commits_since


def build_release_pr_text(
    config: dict,
    bot_name: str,
    skip_marker: str,
    today: str | None = None,
) -> tuple[bool, str, str]:
    """Geef (heeft_wijzigingen, titel, omschrijving) voor de dev -> main PR/MR."""
    today = today or datetime.date.today().isoformat()

    current_tag = semver.get_latest_tag()
    _, next_version = semver.determine_next_version(config["initial_version"])

    commits = cl.filter_meaningful_commits(
        get_commits_since(current_tag),
        config.get("skip_release_when", []),
        extra_markers=[skip_marker],
        bot_name=bot_name,
    )

    title = f"Release {next_version}"

    if not commits:
        body = (
            f"> Automatisch voorbereid. Nog geen inhoudelijke wijzigingen sinds "
            f"`{current_tag or 'begin repo'}`.\n\n"
            "Bij merge naar `main` wordt de release automatisch bepaald."
        )
        return False, title, body

    changelog_entry = cl.build_changelog_entry(next_version, today, commits)
    notes = notes_mod.build_release_notes(next_version, changelog_entry)
    body = (
        f"> Automatisch voorbereid door qlik-git-automation. Versie **{next_version}** "
        "en changelog worden definitief bepaald bij de merge naar `main`.\n\n"
        f"{notes}"
    )
    return True, title, body
