"""qlik_block.py – bouw en injecteer het Qlik 'Log & Version' commentaarblok.

Het blok is een geldig Qlik ``/* ... */`` commentaar zodat een latere Gitoqlok
pull het weer in de app laadt zonder het script te breken (round-trip). De
structuur wordt hier deterministisch gebouwd; optionele AI-polish mag alleen de
tekst herformuleren en wordt daarna opnieuw gevalideerd (zie gemini.py).

Herbruikt find_qlik_changelog_script en update_qlik_changelog uit het
oorspronkelijke pr_automation.py.
"""

from __future__ import annotations

import glob
import os
import re

# Kolombreedtes voor nette uitlijning in het blok. Naam ruim genomen zodat de
# Mutatie-kolom met afstand daarachter begint en de tekst onder elkaar valt.
_COL_VERSION = 16
_COL_DATE = 14
_COL_NAME = 30
_SEP_WIDTH = 120
_SEP = "-" * _SEP_WIDTH

# Herkent een volledig Log & Version blok (voor vervangen / valideren).
BLOCK_RE = re.compile(r"/\*-{5,}.*?Log\s*&\s*Version.*?-{5,}\*/", re.DOTALL | re.IGNORECASE)


# ──────────────────────────────────────────────
# Bestand vinden
# ──────────────────────────────────────────────

def read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def find_qlik_changelog_script(config: dict) -> str | None:
    """Vind het Qlik-scriptbestand met de Changelog-sectie.

    Volgorde: expliciet pad uit config > glob-patronen uit config > elk .qvs
    met een ``///$tab ...<marker>`` header.
    """
    ls = config.get("load_script", {})
    explicit = ls.get("path")
    if explicit and os.path.exists(explicit):
        return explicit

    for pattern in ls.get("glob", []):
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]

    marker = re.escape(ls.get("tab_marker", "Changelog"))
    tab_re = re.compile(rf"///\s*\$tab\s+.*{marker}", re.IGNORECASE)
    for path in glob.glob("**/*.qvs", recursive=True):
        if tab_re.search(read_file(path)):
            return path
    return None


# ──────────────────────────────────────────────
# Blok bouwen
# ──────────────────────────────────────────────

def _format_row(version: str, date: str, name: str, mutation_lines: list[str]) -> list[str]:
    """Eén versieregel + vervolgregels, mutatietekst netjes onder elkaar.

    Alle mutatieregels lijnen uit op de Mutatie-kolom. Past een veld (meestal een
    lange naam) niet in zijn kolom, dan komen álle mutaties op een eigen regel
    daaronder in plaats van de eerste vastgeplakt aan de naam.
    """
    indent_n = _COL_VERSION + _COL_DATE + _COL_NAME
    indent = " " * indent_n
    mutations = mutation_lines or [""]
    prefix = f"{version:<{_COL_VERSION}}{date:<{_COL_DATE}}{name:<{_COL_NAME}}"

    if len(prefix) > indent_n:                       # veld te breed voor kolom
        rows = [prefix.rstrip()]
        rows += [f"{indent}{m}".rstrip() for m in mutations]
        return rows

    first, *rest = mutations
    rows = [f"{prefix}{first}".rstrip()]
    rows += [f"{indent}{m}".rstrip() for m in rest]
    return rows


def parse_existing_rows(block: str) -> list[str]:
    """Haal de bestaande dataregels uit een blok (tussen de twee separators)."""
    if not block:
        return []
    # Alles tussen de eerste separator-na-de-koprij en de afsluitende separator.
    inner = BLOCK_RE.search(block)
    if not inner:
        return []
    body = inner.group(0)
    seps = [m.start() for m in re.finditer(r"-{5,}", body)]
    if len(seps) < 2:
        return []
    start = body.index("\n", seps[-2]) + 1 if "\n" in body[seps[-2]:] else seps[-2]
    end = body.rfind("\n", 0, seps[-1])
    rows = body[start:end].splitlines()
    return [r for r in rows if r.strip()]


def build_qlik_block(
    version: str,
    date: str,
    author: str,
    mutation_lines: list[str],
    previous_block: str = "",
) -> str:
    """Bouw een volledig, geldig Log & Version blok met de nieuwe entry bovenaan.

    Bestaande regels uit ``previous_block`` blijven bewaard onder de nieuwe entry.
    ``version`` mag met of zonder 'v' worden aangeleverd; in het blok staat het
    altijd mét 'v' (bijv. v0.0.1).
    """
    ver = "v" + version.lstrip("v")
    # Voorkom dat gebruikerstekst het commentaar vroegtijdig afsluit.
    safe_mutations = [line.replace("*/", "* /") for line in (mutation_lines or ["-"])]

    new_rows = _format_row(ver, date, author, safe_mutations)
    old_rows = parse_existing_rows(previous_block)
    # Vermijd dubbele entry bij herhaalde run op dezelfde versie.
    old_rows = [r for r in old_rows if not r.startswith(f"{ver} ") and r.strip() != ver]

    lines = [
        f"/*{_SEP}",
        "Log & Version",
        "",
        f"{'Versienummer':<{_COL_VERSION}}{'Datum':<{_COL_DATE}}{'Naam':<{_COL_NAME}}Mutatie",
        _SEP,
        *new_rows,
        *old_rows,
        f"{_SEP}*/",
    ]
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Validatie (round-trip garantie)
# ──────────────────────────────────────────────

def is_valid_block(block: str) -> bool:
    """True als het blok een geldig, gesloten Qlik-commentaar is.

    Vereist: begint met /*, eindigt met */, geen voortijdige */ die het
    commentaar zou sluiten, en herkenbaar als Log & Version blok.
    """
    if not block or not block.startswith("/*") or not block.rstrip().endswith("*/"):
        return False
    inner = block.rstrip()[2:-2]
    if "*/" in inner:
        return False
    return BLOCK_RE.fullmatch(block.strip()) is not None


# ──────────────────────────────────────────────
# Injecteren in het script
# ──────────────────────────────────────────────

def update_qlik_changelog(script_content: str, qlik_block: str, tab_marker: str = "Changelog") -> str:
    """Plaats het blok altijd direct ná de ``///$tab ...<marker>`` regel.

    Behoudt alles vóór en inclusief de $tab-regel, en zet het blok op een eigen
    regel daaronder. Een bestaand blok ná de $tab-regel wordt in-place vervangen.
    De $tab-regel wordt ook herkend als die aan het einde van het bestand staat
    zonder afsluitende newline.
    """
    marker = re.escape(tab_marker)
    # Newline achter de $tab-regel is optioneel (kan laatste regel zijn).
    tab_match = re.search(rf"///\s*\$tab\s+.*{marker}[^\n]*(?:\n|$)", script_content, re.IGNORECASE)
    block_match = BLOCK_RE.search(script_content)

    if tab_match:
        # Normaliseer: $tab-regel + precies één newline, dan het blok.
        tab_line = script_content[tab_match.start():tab_match.end()].rstrip("\n")
        before = script_content[:tab_match.start()] + tab_line + "\n"
        after = script_content[tab_match.end():]

        if block_match and block_match.start() >= tab_match.end():
            # Bestaand blok ná de $tab-regel: in-place vervangen.
            rel_start = block_match.start() - tab_match.end()
            rel_end = block_match.end() - tab_match.end()
            after = after[:rel_start] + qlik_block + after[rel_end:]
            return before + after

        # Geen blok ná de $tab-regel: nieuw blok invoegen, resterende inhoud eronder.
        rest = after.lstrip("\n")
        if rest:
            return before + qlik_block + "\n\n" + rest
        return before + qlik_block + "\n"

    if block_match:
        return script_content[:block_match.start()] + qlik_block + script_content[block_match.end():]
    return qlik_block + "\n\n" + script_content
