"""gemini.py – optionele AI-polish voor release-notes en het Qlik-blok.

Gedrag:
- Zonder ``GEMINI_API_KEY`` in de omgeving zijn alle functies een no-op: de
  deterministische invoer wordt onveranderd teruggegeven. Er is dan geen secret
  nodig en de uitvoer is reproduceerbaar.
- Met een key mag Gemini uitsluitend de *tekst* herformuleren. Voor het Qlik-blok
  wordt de uitkomst opnieuw structureel gevalideerd; bij twijfel valt de functie
  terug op het deterministische blok. Zo kan AI het laadscript nooit breken.
"""

from __future__ import annotations

import os

from . import qlik_block as qb

MODEL = "gemini-2.5-flash"


def _client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        from google import genai
    except ImportError:
        print("  ⚠ google-genai niet geïnstalleerd — AI-polish overgeslagen.")
        return None
    return genai.Client(api_key=api_key)


def _polish_enabled(config: dict, target: str) -> bool:
    return target in (config.get("ai", {}) or {}).get("polish", [])


def _generate(client, prompt: str) -> str | None:
    try:
        resp = client.models.generate_content(model=MODEL, contents=prompt)
        return (resp.text or "").strip()
    except Exception as exc:  # pragma: no cover - netwerk/afhankelijk
        print(f"  ⚠ Gemini-aanroep mislukt ({exc}) — deterministische tekst behouden.")
        return None


def polish_release_notes(notes: str, config: dict) -> str:
    """Herformuleer de prozatekst van de release-notes. No-op zonder key."""
    if not _polish_enabled(config, "release_notes"):
        return notes
    client = _client()
    if client is None:
        return notes
    prompt = (
        "Herschrijf onderstaande release-notes zodat ze prettig leesbaar zijn in "
        "correct Nederlands. Behoud alle Markdown-structuur, koppen en codeblokken "
        "exact; wijzig geen versienummers, datums of het Qlik-codeblok. Geef "
        "uitsluitend de herschreven Markdown terug.\n\n" + notes
    )
    result = _generate(client, prompt)
    return result or notes


def polish_qlik_block(block: str, config: dict) -> str:
    """Herformuleer alleen de mutatietekst in het blok; valideer daarna.

    Bij elke structurele afwijking wordt het originele deterministische blok
    behouden (round-trip garantie).
    """
    if not _polish_enabled(config, "qlik_block"):
        return block
    client = _client()
    if client is None:
        return block
    prompt = (
        "Hieronder staat een Qlik load-script commentaarblok. Verbeter uitsluitend "
        "de leesbaarheid van de omschrijvingen in de kolom 'Mutatie'. Behoud de "
        "exacte structuur: begin- en eindmarkering /* en */, de scheidingslijnen, "
        "de kolomkoppen, versienummers en datums. Voeg nergens */ toe binnen het "
        "blok. Geef uitsluitend het volledige blok terug.\n\n" + block
    )
    result = _generate(client, prompt)
    if result and qb.is_valid_block(result):
        return result
    if result:
        print("  ⚠ AI-blok ongeldig — deterministisch blok behouden.")
    return block
