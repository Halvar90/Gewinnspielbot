"""Vorfilter: stumpf, regelbasiert, kostet nichts.

Die inhaltliche Bewertung macht Claude spaeter ueber MCP. Hier wird nur
offensichtlicher Mist aussortiert, damit die Liste kurz bleibt.
"""
import re
from dataclasses import dataclass

from . import db
from .profil import RELEVANT

_RELEVANT = [re.compile(p, re.I) for p in RELEVANT]


@dataclass
class Urteil:
    durch: bool
    grund: str
    prio: int = 5


def regeln() -> dict[str, list[tuple[re.Pattern, str]]]:
    out: dict[str, list[tuple[re.Pattern, str]]] = {
        "ausschluss": [], "interesse": [], "blocklist": []}
    for r in db.q("SELECT art,muster,grund FROM regel WHERE aktiv"):
        try:
            out.setdefault(r["art"], []).append(
                (re.compile(r["muster"], re.I), r["grund"] or ""))
        except re.error:
            continue
    return out


def pruefe(fund, quelle: dict, rg: dict) -> Urteil:
    titel = fund.titel
    # 1. Ist es ueberhaupt ein Angebot? Nur pruefen, wenn die Quelle
    #    gemischte Inhalte hat (also Stichwoerter definiert sind).
    if quelle.get("keywords"):
        if not any(p.search(titel) for p in _RELEVANT):
            return Urteil(False, "kein Angebots-Stichwort im Titel")
    # 2. Harte Ausschluesse
    for pat, grund in rg.get("ausschluss", []):
        if pat.search(titel):
            return Urteil(False, f"Ausschluss: {grund}")
    for pat, grund in rg.get("blocklist", []):
        if pat.search(titel) or pat.search(fund.url):
            return Urteil(False, f"Blocklist: {grund}")
    # 3. Interessen heben die Prio
    prio = quelle.get("prio") or 5
    treffer = [g for pat, g in rg.get("interesse", []) if pat.search(titel)]
    if treffer:
        prio = min(prio, 2)
        return Urteil(True, "passt: " + ", ".join(treffer[:2]), prio)
    return Urteil(True, "unklar - bitte bewerten", prio)
