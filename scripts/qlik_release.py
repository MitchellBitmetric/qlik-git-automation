"""qlik_release.py – release-flow op merge dev -> main (GitHub én GitLab).

Deterministische stappen:
  1. Bepaal volgende versie (rolling-digit carry vanaf laatste tag).
  2. Verzamel commits sinds de laatste tag (= de zojuist gemergede dev-commits).
  3. Bouw changelog-entry + release-notes + geldig Qlik Log & Version blok.
  4. (optioneel) AI-polish op tekst; het Qlik-blok wordt daarna hervalideerd.
  5. Werk CHANGELOG.md en het Qlik-laadscript bij en commit terug naar main.
  6. Maak git-tag + platform-release.

Loop-beveiliging: als de HEAD-commit al een release-commit is ([skip release]
of bot-auteur) stopt het script direct. Idempotent: dezelfde versie tweemaal
draaien maakt geen tweede tag/commit aan.

Write-back grens: dit script wijzigt uitsluitend het script-BESTAND in git. Het
in de live Qlik-app krijgen gebeurt via een Gitoqlok pull in de browser.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import changelog as cl
from core import gemini
from core import notes as notes_mod
from core import qlik_block as qb
from core import semver
from core.config import load_config
from core.gitutil import (
    configure_bot_identity,
    get_commits_since,
    head_commit_author,
    head_commit_message,
)
from core.platform import detect_platform

BOT_NAME = "qlik-release-bot"
BOT_EMAIL = "qlik-release-bot@users.noreply.github.com"
SKIP_MARKER = "[skip release]"


def read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def write_file(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✔ Geschreven: {path}")


def skip_reason(config: dict) -> str | None:
    """Geef een reden om de release over te slaan, of None om door te gaan.

    Sla over bij: de [skip release]-marker, de release-bot als auteur (loop-
    beveiliging), of wanneer het commit-bericht een van de configureerbare
    'skip_release_when'-patronen bevat (bijv. Gitoqlok-housekeeping).
    """
    try:
        message = head_commit_message()
        author = head_commit_author()
    except subprocess.CalledProcessError:
        return None
    if SKIP_MARKER in message:
        return f"'{SKIP_MARKER}'-marker in commit-bericht"
    if author == BOT_NAME:
        return "commit door de release-bot (loop-beveiliging)"
    for pattern in config.get("skip_release_when", []):
        if pattern and pattern in message:
            return f"commit-bericht bevat '{pattern}'"
    return None


def main() -> int:
    print("── Qlik Release Script ──")

    config = load_config()

    reason = skip_reason(config)
    if reason:
        print(f"  ⏭  Release overgeslagen — {reason}.")
        return 0

    platform = detect_platform()
    today = datetime.date.today().isoformat()
    print(f"  Platform: {platform.name}  Repo: {platform.repo_slug}")

    # 1. Versie bepalen
    current_tag = semver.get_latest_tag()
    _, new_version = semver.determine_next_version(config["initial_version"])
    print(f"  Versie: {current_tag or '(geen tag)'} → {new_version}")

    # Idempotent: bestaat de doel-tag al, dan is er niets te doen.
    existing = subprocess.run(
        ["git", "tag", "--list", new_version], capture_output=True, text=True
    ).stdout.strip()
    if existing:
        print(f"  ⏭  Tag {new_version} bestaat al — release overgeslagen.")
        return 0

    # 2. Commits sinds laatste tag — housekeeping/seed-commits eruit filteren
    commits = cl.filter_meaningful_commits(
        get_commits_since(current_tag),
        config.get("skip_release_when", []),
        extra_markers=[SKIP_MARKER],
        bot_name=BOT_NAME,
    )
    print(f"  {len(commits)} inhoudelijke commit(s) sinds {current_tag or 'begin repo'}")
    author = commits[0].author if commits else platform.repo_slug

    # 3. Deterministisch bouwen
    changelog_entry = cl.build_changelog_entry(new_version, today, commits)

    qlik_path = qb.find_qlik_changelog_script(config)
    mutation_lines = [c.subject for c in commits] or ["Geen wijzigingen"]
    previous_block = ""
    if qlik_path:
        previous_block = ""
        m = qb.BLOCK_RE.search(qb.read_file(qlik_path))
        if m:
            previous_block = m.group(0)
    block = qb.build_qlik_block(new_version, today, author, mutation_lines, previous_block)

    # 4. Optionele AI-polish (tekst) — daarna hervalideren
    block = gemini.polish_qlik_block(block, config)
    if not qb.is_valid_block(block):
        print("  ⚠ Qlik-blok ongeldig na verwerking — deterministisch blok herbouwen.")
        block = qb.build_qlik_block(new_version, today, author, mutation_lines, previous_block)

    release_notes = notes_mod.build_release_notes(new_version, changelog_entry, block)
    release_notes = gemini.polish_release_notes(release_notes, config)

    # 5. Bestanden bijwerken
    write_file("CHANGELOG.md", cl.update_changelog(read_file("CHANGELOG.md"), changelog_entry))
    if qlik_path:
        marker = config["load_script"]["tab_marker"]
        write_file(qlik_path, qb.update_qlik_changelog(read_file(qlik_path), block, marker))
    else:
        print("  ⚠ Geen Qlik-laadscript gevonden — blok opgeslagen als qlik_changelog_block.txt")
        write_file("qlik_changelog_block.txt", block)

    # 6. Commit terug + tag + release
    configure_bot_identity(BOT_NAME, BOT_EMAIL)
    subprocess.run(["git", "add", "-A"], check=True)
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode
    commit_sha = os.environ.get("GITHUB_SHA") or os.environ.get("CI_COMMIT_SHA", "HEAD")
    if staged != 0:  # er zijn wijzigingen
        subprocess.run(
            ["git", "commit", "-m", f"chore(release): {new_version} {SKIP_MARKER}"],
            check=True,
        )
        platform.push_commit(config["main_branch"])
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip()
    else:
        print("  ℹ Geen bestandswijzigingen om te committen.")

    platform.create_tag_push(new_version)
    platform.create_release(new_version, f"Release {new_version}", release_notes, commit_sha)

    print(f"\n✅ Release {new_version} voltooid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
