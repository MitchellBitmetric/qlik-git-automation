"""
create_release.py – GitLab Release aanmaken na merge naar main
================================================================
- Leest het versienummer uit de meest recente entry in CHANGELOG.md
  (geschreven door pr_automation.py tijdens de MR)
- Maakt een git-tag aan met dat versienummer
- Maakt een GitLab Release aan via de API
"""

import os
import re
import glob
import subprocess
import requests

# ──────────────────────────────────────────────
# Omgevingsvariabelen (GitLab CI/CD)
# ──────────────────────────────────────────────
GITLAB_API_TOKEN = os.environ["GITLAB_API_TOKEN"]  # PAT met api-scope
GITLAB_API_URL  = os.environ.get("CI_API_V4_URL", "https://gitlab.com/api/v4")
PROJECT_ID      = os.environ["CI_PROJECT_ID"]
COMMIT_SHA      = os.environ["CI_COMMIT_SHA"]
CI_PROJECT_PATH = os.environ["CI_PROJECT_PATH"]

GL_HEADS = {
    "PRIVATE-TOKEN": GITLAB_API_TOKEN,
    "Content-Type": "application/json",
}

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
    """
    Lees het versienummer uit de eerste ## heading in CHANGELOG.md.
    pr_automation.py schrijft entries als: ## [v0.1.2] - 2026-03-19 !5
    Geeft het versienummer terug inclusief 'v'-prefix.
    """
    content = read_file("CHANGELOG.md")
    if not content:
        print(f"  ⚠ Geen CHANGELOG.md gevonden, gebruik fallback: {FALLBACK_VERSION}")
        return FALLBACK_VERSION

    # Zoek het eerste ## [vX.Y.Z] patroon
    match = re.search(r"^##\s+\[?(v\d+\.\d+\.\d+)\]?", content, re.MULTILINE)
    if match:
        version = match.group(1)
        print(f"  Versie uit CHANGELOG.md: {version}")
        return version

    print(f"  ⚠ Geen versienummer gevonden in CHANGELOG.md, gebruik fallback: {FALLBACK_VERSION}")
    return FALLBACK_VERSION


def tag_already_exists(version: str) -> bool:
    """Controleer of de tag al bestaat om dubbele releases te voorkomen."""
    try:
        result = subprocess.run(
            ["git", "tag", "--list", version],
            capture_output=True, text=True, check=True
        )
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def get_latest_changelog_entry() -> str:
    """Haal de meest recente entry op uit CHANGELOG.md."""
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
    """Lees het huidige /* Log & Version */ blok uit het Qlik laadscript."""
    for pattern in ["**/Changelog.qvs", "**/changelog.qvs"]:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            content = read_file(matches[0])
            m = re.search(r"/\*-{5,}.*?Log\s*&\s*Version.*?-{5,}\*/", content, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(0)
    return ""


# ──────────────────────────────────────────────
# Git-tag & GitLab Release
# ──────────────────────────────────────────────

def create_git_tag(version: str) -> None:
    subprocess.run(["git", "tag", "-a", version, "-m", f"Release {version}"], check=True)
    subprocess.run(["git", "push", "origin", version], check=True)
    print(f"  ✔ Git-tag '{version}' aangemaakt en gepusht")


def create_gitlab_release(version: str, description: str) -> None:
    url  = f"{GITLAB_API_URL}/projects/{PROJECT_ID}/releases"
    body = {
        "name":        f"Release {version}",
        "tag_name":    version,
        "description": description,
        "ref":         COMMIT_SHA,
    }
    resp = requests.post(url, headers=GL_HEADS, json=body, timeout=30)
    if resp.status_code == 201:
        release_url = resp.json().get("_links", {}).get("self", "")
        print(f"  ✔ GitLab Release aangemaakt: {release_url}")
    else:
        print(f"  ✘ Fout bij aanmaken release: {resp.status_code} – {resp.text}")
        resp.raise_for_status()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    print("── Release Script (GitLab) ──")
    print(f"  Project: {CI_PROJECT_PATH}")
    print(f"  Commit:  {COMMIT_SHA[:8]}")

    # 1. Versienummer ophalen uit CHANGELOG.md (geschreven door pr_automation.py)
    print("\n▶ Versienummer ophalen uit CHANGELOG.md …")
    version = get_version_from_changelog()

    # 2. Controleer of tag al bestaat (bescherming tegen dubbele runs)
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

    # 5. GitLab Release aanmaken
    print(f"\n▶ GitLab Release '{version}' aanmaken …")
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
    create_gitlab_release(version, description)

    print(f"\n✅ Release {version} succesvol aangemaakt!")


if __name__ == "__main__":
    main()
