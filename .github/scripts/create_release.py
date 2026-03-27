"""
create_release.py – GitHub Release aanmaken na merge naar main
================================================================
- Leest het versienummer uit de meest recente entry in CHANGELOG.md
- Maakt een git-tag aan met dat versienummer
- Maakt een GitHub Release aan via de API
"""

import os
import re
import glob
import subprocess
import requests

# ──────────────────────────────────────────────
# Omgevingsvariabelen
# ──────────────────────────────────────────────
GITHUB_TOKEN    = os.environ["GITHUB_TOKEN"]
REPO_FULL_NAME  = os.environ["REPO_FULL_NAME"]
COMMIT_SHA      = os.environ["COMMIT_SHA"]
COMMIT_AUTHOR   = os.environ.get("COMMIT_AUTHOR", "onbekend")

GH_API   = "https://api.github.com"
GH_HEADS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

FALLBACK_VERSION = "v0.1.0"


# ──────────────────────────────────────────────
# Hulpfuncties
# ──────────────────────────────────────────────

def read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def get_version_from_changelog() -> str:
    content = read_file("CHANGELOG.md")
    if not content:
        print(f"  ⚠ Geen CHANGELOG.md gevonden, gebruik fallback: {FALLBACK_VERSION}")
        return FALLBACK_VERSION

    match = re.search(r"^##\s+\[?(v\d+\.\d+\.\d+)\]?", content, re.MULTILINE)
    if match:
        version = match.group(1)
        print(f"  Versie uit CHANGELOG.md: {version}")
        return version

    print(f"  ⚠ Geen versienummer gevonden in CHANGELOG.md, gebruik fallback: {FALLBACK_VERSION}")
    return FALLBACK_VERSION


def tag_already_exists(version: str) -> bool:
    try:
        result = subprocess.run(
            ["git", "tag", "--list", version],
            capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def get_latest_changelog_entry() -> str:
    content = read_file("CHANGELOG.md")
    if not content:
        return "Geen changelog beschikbaar."
    matches = list(re.finditer(r"^## ", content, re.MULTILINE))
    if not matches:
        return content.strip() or "Geen changelog beschikbaar."
    start = matches[0].start()
    end   = matches[1].start() if len(matches) > 1 else len(content)
    return content[start:end].strip()


def get_qlik_changelog_block() -> str:
    for pattern in ["**/Changelog.qvs", "**/changelog.qvs"]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            content = read_file(matches[0])
            m = re.search(r"/\*-{5,}.*?Log\s*&\s*Version.*?-{5,}\*/", content, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(0)
    return ""


# ──────────────────────────────────────────────
# Git-tag & GitHub Release
# ──────────────────────────────────────────────

def create_git_tag(version: str) -> None:
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=True)
    subprocess.run(["git", "tag", "-a", version, "-m", f"Release {version}"], check=True)
    subprocess.run(["git", "push", "origin", version], check=True)
    print(f"  ✔ Git-tag '{version}' aangemaakt en gepusht")


def create_github_release(version: str, description: str) -> None:
    url  = f"{GH_API}/repos/{REPO_FULL_NAME}/releases"
    body = {
        "tag_name":         version,
        "name":             f"Release {version}",
        "body":             description,
        "draft":            False,
        "prerelease":       False,
        "target_commitish": COMMIT_SHA,
    }
    resp = requests.post(url, headers=GH_HEADS, json=body, timeout=30)
    if resp.status_code == 201:
        release_url = resp.json().get("html_url", "")
        print(f"  ✔ GitHub Release aangemaakt: {release_url}")
    else:
        print(f"  ✘ Fout bij aanmaken release: {resp.status_code} – {resp.text}")
        resp.raise_for_status()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    print("── Release Script (GitHub) ──")
    print(f"  Repo:   {REPO_FULL_NAME}")
    print(f"  Commit: {COMMIT_SHA[:8]}")

    # 1. Versienummer ophalen uit CHANGELOG.md
    print("\n▶ Versienummer ophalen uit CHANGELOG.md …")
    version = get_version_from_changelog()

    # 2. Controleer of tag al bestaat
    if tag_already_exists(version):
        print(f"  ⚠ Tag '{version}' bestaat al — release overgeslagen.")
        return

    # 3. Changelog-inhoud ophalen
    print("\n▶ Changelog-inhoud ophalen …")
    changelog_entry = get_latest_changelog_entry()
    qlik_block      = get_qlik_changelog_block()

    # 4. Git-tag aanmaken
    print(f"\n▶ Git-tag '{version}' aanmaken …")
    create_git_tag(version)

    # 5. GitHub Release aanmaken
    print(f"\n▶ GitHub Release '{version}' aanmaken …")
    qlik_section = (
        f"\n\n### Qlik Log & Version\n\n```\n{qlik_block}\n```"
        if qlik_block else ""
    )
    description = (
        f"## Wat is er nieuw in {version}?\n\n"
        f"{changelog_entry}"
        f"{qlik_section}\n\n"
        f"---\n"
        f"*Automatisch gegenereerd na merge naar main*"
    )
    create_github_release(version, description)

    print(f"\n✅ Release {version} succesvol aangemaakt!")


if __name__ == "__main__":
    main()