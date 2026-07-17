"""Unit tests voor de portable core. Draai met: python -m pytest tests/ -q"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from core import changelog as cl
from core import qlik_block as qb
from core import semver
from core.config import _deep_merge, DEFAULTS
from core.gitutil import Commit


# ── semver: rolling-digit carry ──────────────────────────────

def test_bump_patch():
    assert semver.bump_version("v0.0.8") == "v0.0.9"


def test_bump_carries_patch_to_minor():
    assert semver.bump_version("v0.0.9") == "v0.1.0"


def test_bump_carries_minor_to_major():
    assert semver.bump_version("v0.9.9") == "v1.0.0"


def test_bump_no_carry():
    assert semver.bump_version("v1.2.3") == "v1.2.4"


def test_bump_rejects_garbage():
    try:
        semver.bump_version("nope")
    except ValueError:
        return
    raise AssertionError("verwacht ValueError")


# ── changelog grouping ───────────────────────────────────────

def _commits():
    return [
        Commit("a1", "feat: add sheet Sales", "Alice"),
        Commit("b2", "fix: correct KPI", "Bob"),
        Commit("c3", "tweak colors", "Carol"),
    ]


def test_changelog_groups_conventional_commits():
    entry = cl.build_changelog_entry("v0.1.0", "2026-07-17", _commits())
    assert "## [v0.1.0] - 2026-07-17" in entry
    assert "### Added" in entry and "add sheet Sales" in entry
    assert "### Fixed" in entry and "correct KPI" in entry
    assert "### Overig" in entry and "tweak colors" in entry


def test_changelog_empty_commits():
    entry = cl.build_changelog_entry("v0.1.0", "2026-07-17", [])
    assert "Geen noemenswaardige wijzigingen" in entry


def test_changelog_update_is_idempotent():
    entry = cl.build_changelog_entry("v0.1.0", "2026-07-17", _commits())
    once = cl.update_changelog("", entry)
    twice = cl.update_changelog(once, entry)
    assert once.count("## [v0.1.0]") == 1
    assert twice.count("## [v0.1.0]") == 1


# ── qlik block: validity, round-trip, injection ──────────────

def test_block_is_valid():
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["feat: x", "fix: y"])
    assert qb.is_valid_block(block)


def test_block_neutralises_comment_terminator():
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["breaks */ here"])
    assert qb.is_valid_block(block)
    assert "breaks * / here" in block


def test_block_preserves_previous_rows():
    first = qb.build_qlik_block("v0.0.9", "2026-07-10", "Bob", ["oude wijziging"])
    second = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["nieuwe wijziging"], first)
    assert "0.0.9" in second and "oude wijziging" in second
    assert "0.1.0" in second and "nieuwe wijziging" in second
    assert qb.is_valid_block(second)


def test_block_no_duplicate_on_rerun():
    first = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    again = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"], first)
    assert again.count("0.1.0 ") <= 1 or again.count("\n0.1.0") == 1


def test_injection_after_tab_marker():
    script = "///$tab Main\nLOAD 1 AS a AUTOGENERATE 1;\n///$tab Changelog\n"
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    out = qb.update_qlik_changelog(script, block, "Changelog")
    assert "///$tab Main" in out and "LOAD 1 AS a" in out          # script intact
    found = qb.BLOCK_RE.search(out)
    assert found and qb.is_valid_block(found.group(0))              # round-trip


def test_injection_replaces_existing_block_in_place():
    block1 = qb.build_qlik_block("v0.0.9", "2026-07-10", "Bob", ["oud"])
    script = f"///$tab Changelog\n{block1}\n"
    block2 = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["nieuw"], block1)
    out = qb.update_qlik_changelog(script, block2, "Changelog")
    assert out.count("/*") == 1 and out.count("*/") == 1           # geen dubbel blok


# ── optionele AI-polish: veiligheid ──────────────────────────

def test_gemini_noop_without_key(monkeypatch):
    from core import gemini
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    assert gemini.polish_qlik_block(block, DEFAULTS) == block


def test_gemini_falls_back_on_invalid_output(monkeypatch):
    from core import gemini
    monkeypatch.setattr(gemini, "_client", lambda: object())      # doe alsof key aanwezig is
    monkeypatch.setattr(gemini, "_generate", lambda c, p: "*/ kapot commentaar")
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    # AI-output is ongeldig -> deterministisch blok behouden
    assert gemini.polish_qlik_block(block, DEFAULTS) == block


def test_gemini_accepts_valid_polished_block(monkeypatch):
    from core import gemini
    valid = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["mooier verwoord"])
    monkeypatch.setattr(gemini, "_client", lambda: object())
    monkeypatch.setattr(gemini, "_generate", lambda c, p: valid)
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    assert gemini.polish_qlik_block(block, DEFAULTS) == valid


# ── config merge ─────────────────────────────────────────────

def test_config_deep_merge_keeps_defaults():
    merged = _deep_merge(DEFAULTS, {"main_branch": "trunk"})
    assert merged["main_branch"] == "trunk"
    assert merged["dev_branch"] == "dev"                           # default behouden
    assert merged["load_script"]["tab_marker"] == "Changelog"
