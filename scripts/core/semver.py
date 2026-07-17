"""semver.py – versiebepaling met rolling-digit carry.

Afwijkend van standaard SemVer rolt elk segment over bij 9:
    v0.0.8 -> v0.0.9 -> v0.1.0   en   v0.9.9 -> v1.0.0
Dit is een bewuste keuze van de gebruiker (zie ADR-0003).

Herbruikt de tag-lookup uit het oorspronkelijke pr_automation.py.
"""

from __future__ import annotations

import re
import subprocess

VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def get_latest_tag() -> str | None:
    """Nieuwste ``v*`` tag volgens version-sort, of None als er geen zijn."""
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-version:refname"],
            capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError:
        return None
    tags = [t.strip() for t in result.stdout.strip().splitlines() if t.strip()]
    return tags[0] if tags else None


def parse_version(version: str) -> tuple[int, int, int]:
    match = VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"Ongeldig versieformaat: '{version}'. Verwacht: vX.Y.Z")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def bump_version(version: str) -> str:
    """Verhoog met één stap, met carry bij segmentwaarde > 9.

    >>> bump_version("v0.0.8")
    'v0.0.9'
    >>> bump_version("v0.0.9")
    'v0.1.0'
    >>> bump_version("v0.9.9")
    'v1.0.0'
    """
    major, minor, patch = parse_version(version)
    patch += 1
    if patch > 9:
        patch = 0
        minor += 1
    if minor > 9:
        minor = 0
        major += 1
    return f"v{major}.{minor}.{patch}"


def determine_next_version(initial_version: str = "v0.0.1") -> tuple[str, str]:
    """Geef (huidige, volgende). Zonder tags: ('v0.0.0', initial_version)."""
    latest = get_latest_tag()
    if latest:
        return latest, bump_version(latest)
    return "v0.0.0", initial_version
