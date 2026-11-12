"""Generischer Scraper: Links sammeln statt CSS-Klassen raten.

Begruendung: Portalseiten aendern ihr Markup oft, aber nicht ihre Link-
Struktur. Wir holen alle <a>, filtern per URL-Regex und Linktext und
lassen den Vorfilter entscheiden. Das bricht seltener als Selektoren.
"""
import datetime as dt
import hashlib
import re
import xml.etree.ElementTree as ET
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .. import config

# Button- und CTA-Texte: taugen nicht als Titel eines Fundes
GENERISCH = re.compile(
    r"^(?:testergebnis(?:se)?|mehr erfahren|mehr infos?|zu den details|"
    r"details|jetzt bewerben|jetzt mitmachen|jetzt testen|hier klicken|"
    r"weiterlesen|zur aktion|teilnehmen|anmelden|mehr dazu|"
    r"alle (?:\w+ )?anzeigen|zum produkt|zum angebot)[\s!.:]*$", re.I)

DATUM = re.compile(
    r"(?:einsendeschluss|teilnahmeschluss|bis(?:\s+zum)?|endet(?:\s+am)?)"
    r"[:\s]*(\d{1,2})\.(\d{1,2})\.(\d{2,4})", re.I)


@dataclass
class Fund:
    titel: str
    url: str
    quelle: str
    kategorie: str = "allgemein"
    frist: str | None = None
    kontext: str = field(default="", repr=False)

    @property
    def url_hash(self) -> str:
        p = urlparse(self.url)
        norm = urlunparse((p.scheme, p.netloc.lower().removeprefix("www."),
                           p.path.rstrip("/"), "", "", ""))
        return hashlib.sha256(norm.encode()).hexdigest()[:32]


def hole(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=config.TIMEOUT,
                      headers={"User-Agent": config.UA,
                               "Accept-Language": "de-DE,de;q=0.9"}) as cl:
        r = cl.get(url)
        r.raise_for_status()
        return r.text


def plausibel(frist: str | None) -> str | None:
    """Verwirft Datumsangaben, die keine Frist sein koennen.

    Der generische Scraper fischt sonst Jahreszahlen aus Testberichten
    (gesehen: 0202-04-24, 2019, 2021) und meldet sie als Frist.
    """
    if not frist:
        return None
    try:
        d = dt.date.fromisoformat(frist)
    except ValueError:
        return None
    heute = dt.date.today()
    if d < heute - dt.timedelta(days=7):
        return None            # zu alt, kann keine offene Frist sein
    if d > heute + dt.timedelta(days=730):
        return None            # mehr als zwei Jahre voraus: unglaubwuerdig
    return frist


def frist_aus_text(text: str) -> str | None:
    m = DATUM.search(text or "")
    if not m:
        return None
    t, mo, j = m.groups()
    j = int(j)
    if j < 100:
        j += 2000
    try:
        return plausibel(f"{j:04d}-{int(mo):02d}-{int(t):02d}")
    except ValueError:
        return None


def aus_rss(quelle: dict, xml_text: str) -> list[Fund]:
    """RSS/Atom lesen. Fuer Seiten, die Scraping abwehren (mydealz:
    Cloudflare-Zwischenseite lieferte still null Treffer)."""
    out, gesehen = [], set()
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise RuntimeError(f"RSS nicht lesbar: {e}")
    knoten = root.iter("item")
    for it in knoten:
        titel = (it.findtext("title") or "").strip()
        url = (it.findtext("link") or "").strip()
        if not titel or not url or len(titel) < 12:
            continue
        f = Fund(titel=" ".join(titel.split())[:200], url=url,
                 quelle=quelle["name"],
                 kategorie=quelle.get("kategorie") or "allgemein")
        if f.url_hash in gesehen:
            continue
        gesehen.add(f.url_hash)
        f.frist = frist_aus_text(it.findtext("description") or "")
        out.append(f)
    return out[:60]


def sammle(quelle: dict, html: str | None = None) -> list[Fund]:
    """Liest eine Quelle und liefert Kandidaten. Wirft bei Netzfehlern."""
    html = html if html is not None else hole(quelle["url"])
    time.sleep(config.HOEFLICH_S)
    if (quelle.get("methode") or "static") == "rss":
        return aus_rss(quelle, html)
    tree = HTMLParser(html)
    pat = re.compile(quelle["link_pattern"], re.I) if quelle.get("link_pattern") else None
    kws = [re.compile(k, re.I) for k in (quelle.get("keywords") or [])]
    selbst = Fund(titel="x", url=quelle["url"], quelle="x").url_hash
    gesehen, out = {selbst}, []

    for a in tree.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(quelle["url"], href)
        titel = " ".join((a.text() or "").split())
        if len(titel) < 12 or len(titel) > 220:
            continue
        if GENERISCH.match(titel):
            continue
        if pat and not pat.search(url):
            continue
        if kws and not any(k.search(titel) for k in kws):
            continue
        f = Fund(titel=titel[:200], url=url, quelle=quelle["name"],
                 kategorie=quelle.get("kategorie") or "allgemein")
        if f.url_hash in gesehen:
            continue
        gesehen.add(f.url_hash)
        # Umfeld des Links nach einer Frist durchsuchen
        node, ctx = a.parent, ""
        for _ in range(4):
            if node is None:
                break
            ctx = " ".join((node.text() or "").split())[:600]
            if DATUM.search(ctx):
                break
            node = node.parent
        f.kontext = ctx
        f.frist = frist_aus_text(ctx) or frist_aus_text(titel)
        out.append(f)
    return out[:60]


GESCHLOSSEN = re.compile(
    r"bewerbungsphase (?:ist )?(?:beendet|abgeschlossen|vorbei)"
    r"|bewerbung(?:en)? (?:ist|sind) (?:nicht mehr|leider nicht)"
    r"|aktion (?:ist )?(?:beendet|abgelaufen)"
    r"|das sind die tester|die tester stehen"
    r"|gewinner stehen fest|teilnahmeschluss war"
    r"|bewerbungsschluss war|leider (?:schon )?vorbei"
    r"|bewerbungsfrist[^.]{0,60}abgelaufen"   # techrush-Wortlaut
    r"|aktion beendet", re.I)

# Erkennt auf der Detailseite, dass ein Kauf noetig ist. Gelernt an
# BiFi: kostenlos.de titelt "gratis testen", die Aktionsseite ist eine
# Cashback-Aktion mit Kassenbon und IBAN.
KAUF = re.compile(
    r"cashback|kaufpreis (?:wird )?(?:zur[uü]ck )?erstatt|kaufbeleg|"
    r"kassenbon|geld.?zur[uü]ck|erstattung|iban|"
    r"produkt kaufen und", re.I)

FRIST_DETAIL = re.compile(
    r"(?:einsendeschluss|teilnahmeschluss|bewerbungsschluss|bewerbungsfrist"
    r"|bewerben bis|bewerbung bis|l[äa]uft bis|endet am|bis zum)"
    r"[:\s]*(\d{1,2})\.(\d{1,2})\.(\d{2,4})", re.I)


def detail(url: str) -> tuple[str | None, str | None]:
    """Detailseite lesen. Liefert (frist, geschlossen_grund).

    Nur fuer neue Kandidaten aufrufen - kostet einen Request pro Fund.
    """
    try:
        html = hole(url)
    except Exception as e:
        return None, None  # Netzfehler ist kein Ausschluss
    time.sleep(config.HOEFLICH_S)
    text = " ".join(HTMLParser(html).text().split())[:20000]
    zu = GESCHLOSSEN.search(text) or KAUF.search(text)
    m = FRIST_DETAIL.search(text)
    frist = None
    if m:
        t, mo, j = m.groups()
        j = int(j)
        if j < 100:
            j += 2000
        try:
            frist = plausibel(f"{j:04d}-{int(mo):02d}-{int(t):02d}")
        except ValueError:
            frist = None
    return frist, (zu.group(0)[:60] if zu else None)
