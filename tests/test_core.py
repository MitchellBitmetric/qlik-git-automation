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


def test_filter_removes_housekeeping_and_seed_and_bot():
    commits = [
        Commit("a1", "feat: echt dashboard", "Alice"),
        Commit("b2", "Update branches table", "Alice"),
        Commit("c3", "chore: workflow-bestanden toegevoegd via qlik-git-automation [skip release]", "Alice"),
        Commit("d4", "Gitoqlok: auto-restore app properties after merge", "Bob"),
        Commit("e5", "chore(release): v0.0.1 [skip release]", "qlik-release-bot"),
        Commit("f6", "fix: echte bugfix", "Bob"),
    ]
    kept = cl.filter_meaningful_commits(
        commits,
        ["Gitoqlok: auto-restore app properties after merge", "Update branches table"],
        extra_markers=["[skip release]"],
        bot_name="qlik-release-bot",
    )
    assert [c.subject for c in kept] == ["feat: echt dashboard", "fix: echte bugfix"]


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


def _block_directly_after_tab(out: str, marker="Changelog") -> bool:
    """True als het /* ... */ blok op de regel(s) direct ná de $tab-regel staat."""
    lines = out.splitlines()
    for i, line in enumerate(lines):
        if "$tab" in line and marker in line:
            # Eerstvolgende niet-lege regel moet de blokopening zijn.
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            return j < len(lines) and lines[j].startswith("/*")
    return False


def test_injection_block_directly_after_tab_at_eof():
    # $tab-regel is de laatste regel, zónder afsluitende newline.
    script = "///$tab Main\nLOAD 1 AS a AUTOGENERATE 1;\n///$tab Changelog"
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    out = qb.update_qlik_changelog(script, block, "Changelog")
    assert _block_directly_after_tab(out)
    assert qb.is_valid_block(qb.BLOCK_RE.search(out).group(0))


def test_injection_block_after_tab_with_emoji_prefix():
    script = "///$tab 📝 Changelog\n"
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    out = qb.update_qlik_changelog(script, block, "Changelog")
    assert _block_directly_after_tab(out)


def test_injection_block_after_tab_preserves_following_content():
    # Er staat script ná de Changelog-tab; blok moet direct onder de tab,
    # de overige inhoud blijft eronder staan.
    script = "///$tab Changelog\n///$tab Extra\nLOAD 2 AS b AUTOGENERATE 1;\n"
    block = qb.build_qlik_block("v0.1.0", "2026-07-17", "Alice", ["x"])
    out = qb.update_qlik_changelog(script, block, "Changelog")
    assert _block_directly_after_tab(out)
    assert "///$tab Extra" in out and "LOAD 2 AS b" in out       # inhoud behouden
    # Volgorde: Changelog-tab -> blok -> Extra-tab
    assert out.index("$tab Changelog") < out.index("/*") < out.index("$tab Extra")


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


# ── release-PR/MR tekst (gedeeld GitHub + GitLab) ────────────

def test_release_pr_text_filters_and_titles(monkeypatch):
    from core import release_pr, semver
    from core.gitutil import get_commits_since  # noqa: F401
    monkeypatch.setattr(release_pr.semver, "get_latest_tag", lambda: "v0.0.9")
    monkeypatch.setattr(
        release_pr.semver, "determine_next_version", lambda iv: ("v0.0.9", "v0.1.0")
    )
    monkeypatch.setattr(release_pr, "get_commits_since", lambda ref: [
        Commit("a1", "feat: nieuw dashboard", "Alice"),
        Commit("b2", "Update branches table", "Alice"),
    ])
    cfg = {"initial_version": "v0.0.1",
           "skip_release_when": ["Update branches table"]}
    has_changes, title, body = release_pr.build_release_pr_text(
        cfg, "qlik-release-bot", "[skip release]", today="2026-07-17"
    )
    assert has_changes is True
    assert title == "Release v0.1.0"
    assert "nieuw dashboard" in body
    assert "Update branches table" not in body


def test_release_pr_text_no_changes(monkeypatch):
    from core import release_pr
    monkeypatch.setattr(release_pr.semver, "get_latest_tag", lambda: "v0.1.0")
    monkeypatch.setattr(
        release_pr.semver, "determine_next_version", lambda iv: ("v0.1.0", "v0.1.1")
    )
    monkeypatch.setattr(release_pr, "get_commits_since", lambda ref: [])
    has_changes, title, body = release_pr.build_release_pr_text(
        {"initial_version": "v0.0.1"}, "qlik-release-bot", "[skip release]"
    )
    assert has_changes is False
    assert title == "Release v0.1.1"


# ── config merge ─────────────────────────────────────────────

def test_config_deep_merge_keeps_defaults():
    merged = _deep_merge(DEFAULTS, {"main_branch": "trunk"})
    assert merged["main_branch"] == "trunk"
    assert merged["dev_branch"] == "dev"                           # default behouden
    assert merged["load_script"]["tab_marker"] == "Changelog"
