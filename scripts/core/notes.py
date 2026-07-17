"""notes.py – stel de release-notes body samen.

Deterministisch opgebouwd uit de changelog-entry en (optioneel) het Qlik-blok.
Overgenomen uit de body-opbouw van het oorspronkelijke create_release.py.
"""

from __future__ import annotations


def build_release_notes(version: str, changelog_entry: str, qlik_block: str = "") -> str:
    qlik_section = (
        f"\n\n### Qlik Log & Version\n\n```\n{qlik_block}\n```"
        if qlik_block else ""
    )
    return (
        f"## Wat is er nieuw in {version}?\n\n"
        f"{changelog_entry.strip()}"
        f"{qlik_section}\n\n"
        f"---\n"
        f"*Automatisch gegenereerd na merge naar main*"
    )
