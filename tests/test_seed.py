"""Tests voor de seed/scan-beslislogica in init_repo.py (zonder netwerk)."""

import os
import sys

os.environ.setdefault("GH_TOKEN", "x")
os.environ.setdefault("ORG_NAME", "acme")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".github", "scripts"))

import init_repo as ir


def test_seed_skips_repo_without_marker():
    info = {"description": "gewone repo", "default_branch": "main"}
    assert ir.seed_repo("plain", info) is False


def test_seed_runs_for_marked_repo(monkeypatch):
    calls = []
    monkeypatch.setattr(ir, "push_file", lambda *a, **k: calls.append(("push", a[1])))
    monkeypatch.setattr(ir, "ensure_dev_branch", lambda *a, **k: calls.append(("dev", None)))
    monkeypatch.setattr(ir, "protect_main", lambda *a, **k: calls.append(("protect", None)))
    info = {"description": "Sales %gitoqlok_repo%", "default_branch": "main"}
    assert ir.seed_repo("sales", info) is True
    kinds = [c[0] for c in calls]
    assert kinds.count("push") == 3          # 2 workflows + config
    assert "dev" in kinds and "protect" in kinds


def test_scan_seeds_only_marked_and_unseen(monkeypatch):
    repos = [
        {"name": "sales", "description": "%gitoqlok_repo%", "default_branch": "main"},
        {"name": "plain", "description": "geen marker", "default_branch": "main"},
        {"name": "already", "description": "%gitoqlok_repo%", "default_branch": "main"},
    ]
    seeded = []
    monkeypatch.setattr(ir, "list_org_repos", lambda: repos)
    # 'already' geldt als reeds geseed
    monkeypatch.setattr(ir, "file_exists", lambda repo, path, branch: repo == "already")
    monkeypatch.setattr(ir, "seed_repo", lambda repo, info: seeded.append(repo) or True)

    ir.scan_org()
    assert seeded == ["sales"]               # plain: geen marker, already: al geseed
