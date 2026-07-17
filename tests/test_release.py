"""Tests voor de release-skip-logica (welke commits geen release veroorzaken)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import qlik_release as qr
from core.config import DEFAULTS


def _patch_head(monkeypatch, message, author="Alice"):
    monkeypatch.setattr(qr, "head_commit_message", lambda: message)
    monkeypatch.setattr(qr, "head_commit_author", lambda: author)


def test_skip_on_marker(monkeypatch):
    _patch_head(monkeypatch, "chore(release): v0.0.2 [skip release]")
    assert qr.skip_reason(DEFAULTS) is not None


def test_skip_on_bot_author(monkeypatch):
    _patch_head(monkeypatch, "gewone merge", author=qr.BOT_NAME)
    assert qr.skip_reason(DEFAULTS) is not None


def test_skip_on_gitoqlok_housekeeping(monkeypatch):
    _patch_head(monkeypatch, "Gitoqlok: auto-restore app properties after merge")
    assert qr.skip_reason(DEFAULTS) is not None


def test_skip_on_update_branches_table(monkeypatch):
    _patch_head(monkeypatch, "Update branches table")
    assert qr.skip_reason(DEFAULTS) is not None


def test_skip_on_seed_commit(monkeypatch):
    _patch_head(monkeypatch, "chore: workflow-bestanden toegevoegd via qlik-git-automation [skip release]")
    assert qr.skip_reason(DEFAULTS) is not None


def test_no_skip_on_real_merge(monkeypatch):
    _patch_head(monkeypatch, "Merge pull request #3 from dev")
    assert qr.skip_reason(DEFAULTS) is None


def test_skip_pattern_is_configurable(monkeypatch):
    _patch_head(monkeypatch, "chore: reload metadata only")
    cfg = dict(DEFAULTS, skip_release_when=["reload metadata only"])
    assert qr.skip_reason(cfg) is not None
