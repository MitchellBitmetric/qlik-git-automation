"""qlik_release_pr.py – vult titel + omschrijving van de dev -> main PR.

Draait op elke push naar de dev-branch. Berekent deterministisch wat de
volgende release wordt (rolling-digit carry) en welke changelog daarbij hoort,
en schrijft die naar GITHUB_OUTPUT zodat de workflow de dev -> main PR kan
aanmaken of bijwerken via de GitHub CLI.

Maakt zelf GEEN PR, tag of release aan — puur berekenen + tekst leveren.
Loop-beveiligd: bot-commits en [skip release]-commits tellen niet mee.
"""

from __future__ import annotations

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import changelog as cl
from core import notes as notes_mod
from core import semver
from core.config import load_config
from core.gitutil import get_commits_since
from qlik_release import BOT_NAME, SKIP_MARKER


def _emit(name: str, value: str) -> None:
    """Schrijf een (multiline) output-waarde naar GITHUB_OUTPUT."""
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        print(f"{name}={value}")
        return
    delim = f"__EOF_{name}__"
    with open(out, "a", encoding="utf-8") as f:
        f.write(f"{name}<<{delim}\n{value}\n{delim}\n")


def main() -> int:
    print("── Dev -> main PR voorbereiden ──")

    config = load_config()
    today = datetime.date.today().isoformat()

    current_tag = semver.get_latest_tag()
    _, next_version = semver.determine_next_version(config["initial_version"])

    commits = cl.filter_meaningful_commits(
        get_commits_since(current_tag),
        config.get("skip_release_when", []),
        extra_markers=[SKIP_MARKER],
        bot_name=BOT_NAME,
    )
    print(f"  {len(commits)} inhoudelijke commit(s) sinds {current_tag or 'begin repo'}")

    title = f"Release {next_version}"
    if not commits:
        _emit("has_changes", "false")
        _emit("title", title)
        _emit("body", (
            f"> Automatisch voorbereid. Nog geen inhoudelijke wijzigingen sinds "
            f"`{current_tag or 'begin repo'}`.\n\n"
            "Bij merge naar `main` wordt de release automatisch bepaald."
        ))
        print("  ℹ Geen inhoudelijke commits — lege PR-omschrijving.")
        return 0

    changelog_entry = cl.build_changelog_entry(next_version, today, commits)
    body = notes_mod.build_release_notes(next_version, changelog_entry)
    body = (
        f"> Automatisch voorbereid door qlik-git-automation. Versie **{next_version}** "
        "en changelog worden definitief bepaald bij de merge naar `main`.\n\n"
        f"{body}"
    )

    _emit("has_changes", "true")
    _emit("title", title)
    _emit("body", body)
    print(f"  ✔ PR-tekst klaar voor {next_version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
