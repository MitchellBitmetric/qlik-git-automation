"""qlik_preview.py – changelog-preview op een PR/MR (feature -> dev).

Lichte, deterministische variant van de release-flow: berekent wat de volgende
versie zou worden en werkt CHANGELOG.md + het Qlik-blok op de PR/MR-branch bij,
zodat reviewers de wijziging in de diff zien. Maakt GEEN tag of release aan —
dat gebeurt pas bij merge dev -> main via qlik_release.py.

Geen AI nodig. Loop-beveiligd via [skip release]-marker.
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import changelog as cl
from core import qlik_block as qb
from core import semver
from core.config import load_config
from core.gitutil import configure_bot_identity, get_commits_since, head_commit_message
from qlik_release import BOT_EMAIL, BOT_NAME, SKIP_MARKER, read_file, write_file


def main() -> int:
    print("── Qlik Changelog Preview (PR/MR) ──")

    if SKIP_MARKER in head_commit_message():
        print("  ⏭  Laatste commit is een automatische update — overslaan.")
        return 0

    config = load_config()
    today = datetime.date.today().isoformat()
    dev_branch = config["dev_branch"]

    # Basis = integratiebranch; commits op deze branch die daar nog niet in zitten.
    base_ref = None
    for candidate in (f"origin/{dev_branch}", dev_branch):
        check = subprocess.run(
            ["git", "rev-parse", "--verify", candidate], capture_output=True, text=True
        )
        if check.returncode == 0:
            base_ref = candidate
            break

    _, next_version = semver.determine_next_version(config["initial_version"])
    commits = get_commits_since(base_ref)
    print(f"  Preview versie: {next_version}  ({len(commits)} commit(s) t.o.v. {base_ref or 'begin'})")
    if not commits:
        print("  ℹ Geen nieuwe commits — niets te previewen.")
        return 0

    author = commits[0].author
    changelog_entry = cl.build_changelog_entry(next_version, today, commits)

    qlik_path = qb.find_qlik_changelog_script(config)
    previous_block = ""
    if qlik_path:
        m = qb.BLOCK_RE.search(qb.read_file(qlik_path))
        if m:
            previous_block = m.group(0)
    block = qb.build_qlik_block(next_version, today, author, [c.subject for c in commits], previous_block)

    write_file("CHANGELOG.md", cl.update_changelog(read_file("CHANGELOG.md"), changelog_entry))
    if qlik_path:
        marker = config["load_script"]["tab_marker"]
        write_file(qlik_path, qb.update_qlik_changelog(read_file(qlik_path), block, marker))

    configure_bot_identity(BOT_NAME, BOT_EMAIL)
    subprocess.run(["git", "add", "-A"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0:
        subprocess.run(
            ["git", "commit", "-m", f"chore: changelog-preview {next_version} {SKIP_MARKER}"],
            check=True,
        )
        print("  ✔ Preview-commit aangemaakt (push door CI).")
    else:
        print("  ℹ Geen wijzigingen om te committen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
