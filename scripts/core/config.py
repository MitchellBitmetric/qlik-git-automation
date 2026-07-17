"""config.py – laadt het ene consumer-configbestand (qlik-release.yml).

Het configbestand is optioneel: als het ontbreekt of onvolledig is, gelden de
defaults hieronder. Zo blijft adoptie 'near-zero setup': een repo hoeft alleen
af te wijken van de standaard wanneer dat nodig is.
"""

from __future__ import annotations

import os
from typing import Any

try:
    import yaml  # PyYAML
except ImportError:  # pragma: no cover - yaml hoort in CI aanwezig te zijn
    yaml = None

DEFAULTS: dict[str, Any] = {
    "main_branch": "main",
    "dev_branch": "dev",
    "load_script": {
        "path": "",
        "glob": ["**/Changelog.qvs", "**/*changelog*.qvs"],
        "tab_marker": "Changelog",
    },
    "initial_version": "v0.0.1",
    # Commit-berichten die géén release mogen veroorzaken (naast de automatische
    # [skip release]-marker en bot-commits). Bedoeld voor Gitoqlok-housekeeping.
    "skip_release_when": [
        "Gitoqlok: auto-restore app properties after merge",
        "Update branches table",
        "Gitoqlok initial commit",
    ],
    "ai": {
        "polish": ["release_notes", "qlik_block"],
    },
}

CONFIG_FILENAMES = ("qlik-release.yml", "qlik-release.yaml", ".qlik-release.yml")


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursief samenvoegen; waarden uit ``override`` winnen."""
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def find_config_file(root: str = ".") -> str | None:
    for name in CONFIG_FILENAMES:
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):
            return candidate
    return None


def load_config(root: str = ".") -> dict[str, Any]:
    """Laad de config met defaults als basis.

    Ontbrekende sleutels vallen terug op ``DEFAULTS``. Een ontbrekend bestand is
    geen fout – dan gelden volledig de defaults.
    """
    path = find_config_file(root)
    if not path:
        return dict(DEFAULTS)

    if yaml is None:
        raise RuntimeError(
            "PyYAML is niet geïnstalleerd maar er is wel een configbestand "
            f"gevonden ({path}). Installeer met 'pip install pyyaml'."
        )

    with open(path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}

    return _deep_merge(DEFAULTS, user_cfg)
