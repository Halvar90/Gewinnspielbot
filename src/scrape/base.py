"""Generischer Scraper: Links sammeln statt CSS-Klassen raten.

Begruendung: Portalseiten aendern ihr Markup oft, aber nicht ihre Link-
Struktur. Wir holen alle <a>, filtern per URL-Regex und Linktext und
lassen den Vorfilter entscheiden. Das bricht seltener als Selektoren.
"""
import hashlib
import re
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .. import config

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


def frist_aus_text(text: str) -> str | None:
    m = DATUM.search(text or "")
    if not m:
        return None
    t, mo, j = m.groups()
    j = int(j)
    if j < 100:
        j += 2000
    try:
        return f"{j:04d}-{int(mo):02d}-{int(t):02d}"
    except ValueError:
        return None


def sammle(quelle: dict, html: str | None = None) -> list[Fund]:
    """Liest eine Quelle und liefert Kandidaten. Wirft bei Netzfehlern."""
    html = html if html is not None else hole(quelle["url"])
    time.sleep(config.HOEFLICH_S)
    tree = HTMLParser(html)
    pat = re.compile(quelle["link_pattern"], re.I) if quelle.get("link_pattern") else None
    kws = [re.compile(k, re.I) for k in (quelle.get("keywords") or [])]
    gesehen, out = set(), []

    for a in tree.css("a"):
        href = (a.attributes.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        url = urljoin(quelle["url"], href)
        titel = " ".join((a.text() or "").split())
        if len(titel) < 12 or len(titel) > 220:
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
