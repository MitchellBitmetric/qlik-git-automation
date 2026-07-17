"""qlik_release_pr.py – vult titel + omschrijving van de dev -> main PR (GitHub).

Draait op elke push naar de dev-branch. Berekent deterministisch (via de gedeelde
core.release_pr) wat de volgende release wordt en welke changelog daarbij hoort,
en schrijft die naar GITHUB_OUTPUT zodat de workflow de dev -> main PR kan
aanmaken of bijwerken via de GitHub CLI.

Maakt zelf GEEN PR, tag of release aan — puur berekenen + tekst leveren.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import load_config
from core.release_pr import build_release_pr_text
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
    print("── Dev -> main PR voorbereiden (GitHub) ──")

    config = load_config()
    has_changes, title, body = build_release_pr_text(config, BOT_NAME, SKIP_MARKER)

    _emit("has_changes", "true" if has_changes else "false")
    _emit("title", title)
    _emit("body", body)
    print(f"  ✔ PR-tekst klaar: {title}"
          + ("" if has_changes else "  (geen inhoudelijke commits)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
