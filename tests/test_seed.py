"""Tests voor de seed/scan-beslislogica in init_repo.py (zonder netwerk)."""

import os
import sys

os.environ.setdefault("GH_TOKEN", "x")
os.environ.setdefault("ORG_NAME", "acme")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".github", "scripts"))

import init_repo as ir


def test_seed_skips_repo_without_marker():
    info = {"description": "gewone repo", "default_branch": "main"}
    assert ir.seed_repo("acme", "plain", info) is False


def test_seed_runs_for_marked_repo(monkeypatch):
    calls = []
    monkeypatch.setattr(ir, "push_file", lambda org, repo, path, *a, **k: calls.append(("push", path)))
    monkeypatch.setattr(ir, "ensure_dev_branch", lambda *a, **k: calls.append(("dev", None)))
    monkeypatch.setattr(ir, "protect_main", lambda *a, **k: calls.append(("protect", None)))
    monkeypatch.setattr(ir, "protect_dev", lambda *a, **k: calls.append(("protect_dev", None)))
    monkeypatch.setattr(ir, "disable_delete_branch_on_merge", lambda *a, **k: calls.append(("no_delete", None)))
    info = {"description": "Sales %gitoqlok_repo%", "default_branch": "main"}
    assert ir.seed_repo("acme", "sales", info) is True
    kinds = [c[0] for c in calls]
    pushed = [c[1] for c in calls if c[0] == "push"]
    assert kinds.count("push") == 5          # 3 workflows + config + PR-template
    assert ".github/pull_request_template.md" in pushed
    assert ".github/workflows/release-pr.yml" in pushed
    assert "dev" in kinds and "protect" in kinds
    assert "protect_dev" in kinds and "no_delete" in kinds


def test_seed_uses_automation_org_in_caller(monkeypatch):
    pushed = {}
    monkeypatch.setattr(ir, "push_file",
                        lambda org, repo, path, content, branch: pushed.setdefault(path, content))
    monkeypatch.setattr(ir, "ensure_dev_branch", lambda *a, **k: None)
    monkeypatch.setattr(ir, "protect_main", lambda *a, **k: None)
    monkeypatch.setattr(ir, "protect_dev", lambda *a, **k: None)
    monkeypatch.setattr(ir, "disable_delete_branch_on_merge", lambda *a, **k: None)
    monkeypatch.setattr(ir, "AUTOMATION_ORG", "bitmetric-bv")     # centraal model
    info = {"description": "%gitoqlok_repo%", "default_branch": "main"}
    ir.seed_repo("klant-org", "sales", info)
    release = pushed[".github/workflows/release.yml"]
    assert "uses: bitmetric-bv/qlik-git-automation" in release
    assert "automation_repo: bitmetric-bv/qlik-git-automation" in release


def test_scan_seeds_only_marked_and_unseen(monkeypatch):
    repos = [
        {"name": "sales", "description": "%gitoqlok_repo%", "default_branch": "main"},
        {"name": "plain", "description": "geen marker", "default_branch": "main"},
        {"name": "already", "description": "%gitoqlok_repo%", "default_branch": "main"},
    ]
    seeded = []
    monkeypatch.setattr(ir, "list_org_repos", lambda org: repos)
    # 'already' geldt als reeds geseed
    monkeypatch.setattr(ir, "file_exists", lambda org, repo, path, branch: repo == "already")
    monkeypatch.setattr(ir, "seed_repo", lambda org, repo, info: seeded.append(repo) or True)

    ir.scan_org("acme")
    assert seeded == ["sales"]               # plain: geen marker, already: al geseed
