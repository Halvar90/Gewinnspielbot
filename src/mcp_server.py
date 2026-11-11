"""MCP-Server fuer Claude (Custom Connector, Streamable HTTP).

Connector-URL:  https://<railway-domain>/mcp/<MCP_SECRET>
Der geheime Pfad ersetzt eine Anmeldung - er gehoert in keine Mail und
in keinen Chat. Wer ihn hat, kann den Bot steuern.
"""
import datetime as dt
import json

from mcp.server.fastmcp import FastMCP

from . import config, db, notify
from .fristen import faellig
from .run_check import lauf

STATUS = ("neu", "gemeldet", "beworben", "wartet_auf_uwe", "verworfen",
          "gewonnen", "erledigt")

mcp = FastMCP(
    "gratis-scout",
    instructions=(
        "Uwes Bot fuer Gratisproben, Produkttests und Gewinnspiele. "
        "Der Bot sammelt und filtert stumpf; die Bewertung machst du. "
        "Arbeitsweise: funde_liste('neu'/'gemeldet') lesen, je Fund mit "
        "fund_status entscheiden (beworben / wartet_auf_uwe / verworfen) "
        "und den Grund in die Notiz schreiben. Neue Quellen mit "
        "quelle_anlegen eintragen, dauerhafte Ausschluesse mit "
        "regel_anlegen. Uwe: 204 cm, maennlich, Glatze, kein Kaffee, "
        "2 Katzen (nur Trockenfutter), Schwerpunkt PC-Hardware und "
        "Werkzeug, kauft bei Lidl."),
    host="0.0.0.0", port=config.PORT, stateless_http=True,
    streamable_http_path=f"/mcp/{config.MCP_SECRET}" if config.MCP_SECRET else "/mcp",
)


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str, indent=1)


# ---------------------------------------------------------------- lesen
@mcp.tool()
def funde_liste(status: str = "gemeldet", tage: int = 14,
                kategorie: str = "", limit: int = 40) -> str:
    """Funde auflisten. status: neu|gemeldet|beworben|wartet_auf_uwe|
    verworfen|gewonnen|erledigt|alle. tage = wie weit zurueck."""
    sql = ["SELECT id,titel,url,quelle,kategorie,frist,status,vorfilter,"
           "notiz,gefunden FROM fund WHERE gefunden > now() - %s::interval"]
    p: list = [f"{max(tage, 1)} days"]
    if status and status != "alle":
        sql.append("AND status = %s")
        p.append(status)
    if kategorie:
        sql.append("AND kategorie = %s")
        p.append(kategorie)
    sql.append("ORDER BY gefunden DESC LIMIT %s")
    p.append(min(limit, 100))
    return _j(db.q(" ".join(sql), tuple(p)))


@mcp.tool()
def fund_details(fund_id: int) -> str:
    """Einen Fund mit allen Feldern holen."""
    return _j(db.q1("SELECT * FROM fund WHERE id=%s", (fund_id,)) or {})


@mcp.tool()
def fristen(vorlauf_tage: int = 3) -> str:
    """Was ist faellig: taegliche Tuerchen, ablaufende Fristen, offene Funde."""
    return _j(faellig(vorlauf_tage))


@mcp.tool()
def quellen_status() -> str:
    """Alle Quellen mit letztem Lauf und Fehlern - zeigt kaputte Scraper."""
    return _j(db.q("""SELECT name,url,kategorie,prio,aktiv,letzter_lauf,
                      fehler_serie,letzter_fehler FROM quelle
                      ORDER BY fehler_serie DESC, prio"""))


@mcp.tool()
def log(laeufe: int = 5) -> str:
    """Die letzten Laeufe mit Zahlen und Details je Quelle."""
    return _j(db.q("SELECT * FROM lauf ORDER BY id DESC LIMIT %s",
                   (min(laeufe, 30),)))


@mcp.tool()
def regeln_liste() -> str:
    """Aktuelle Filterregeln (Ausschluesse, Interessen, Blocklist)."""
    return _j(db.q("SELECT id,art,muster,grund,aktiv FROM regel ORDER BY art,id"))


# -------------------------------------------------------------- schreiben
@mcp.tool()
def fund_status(fund_id: int, status: str, notiz: str = "",
                bewertung: str = "") -> str:
    """Status eines Fundes setzen. status muss einer von: neu, gemeldet,
    beworben, wartet_auf_uwe, verworfen, gewonnen, erledigt."""
    if status not in STATUS:
        return f"Fehler: status muss aus {STATUS} sein"
    r = db.q1("""UPDATE fund SET status=%s,
                 notiz=COALESCE(NULLIF(%s,''),notiz),
                 bewertung=COALESCE(NULLIF(%s,''),bewertung),
                 geaendert=now() WHERE id=%s RETURNING id,titel,status""",
              (status, notiz, bewertung, fund_id))
    return _j(r or {"fehler": "kein Fund mit dieser id"})


@mcp.tool()
def frist_anlegen(titel: str, faellig_am: str, url: str = "",
                  taeglich: bool = False, notiz: str = "") -> str:
    """Frist eintragen. faellig_am als JJJJ-MM-TT. taeglich=True fuer
    Adventskalender-Tuerchen und wiederholbare Suchbilder."""
    try:
        dt.date.fromisoformat(faellig_am)
    except ValueError:
        return "Fehler: faellig_am als JJJJ-MM-TT angeben"
    r = db.q1("""INSERT INTO frist (titel,url,faellig,taeglich,notiz)
                 VALUES (%s,NULLIF(%s,''),%s,%s,NULLIF(%s,''))
                 RETURNING id,titel,faellig,taeglich""",
              (titel, url, faellig_am, taeglich, notiz))
    return _j(r)


@mcp.tool()
def frist_erledigt(frist_id: int, datum: str = "") -> str:
    """Frist abhaken. Bei taeglichen Fristen gilt das nur fuer diesen Tag."""
    tag = datum or dt.date.today().isoformat()
    r = db.q1("""UPDATE frist SET erledigt_am=%s WHERE id=%s
                 RETURNING id,titel,taeglich,erledigt_am""", (tag, frist_id))
    return _j(r or {"fehler": "keine Frist mit dieser id"})


@mcp.tool()
def quelle_anlegen(name: str, url: str, kategorie: str = "allgemein",
                   link_pattern: str = "", keywords: str = "",
                   prio: int = 5) -> str:
    """Neue Quelle eintragen; wird ab dem naechsten Lauf mitgeprueft.
    link_pattern = Regex auf die Ziel-URL (z.B. '/gewinnspiel/\\d+').
    keywords = kommagetrennte Stichwoerter, die im Linktext stehen muessen
    (leer lassen, wenn die Seite ohnehin nur Angebote listet).
    prio 1 = eilig (taegliche Deadline), 5 = normal."""
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    r = db.q1("""INSERT INTO quelle (name,url,kategorie,link_pattern,keywords,prio)
                 VALUES (%s,%s,%s,NULLIF(%s,''),%s,%s)
                 ON CONFLICT (name) DO UPDATE SET url=EXCLUDED.url,
                   kategorie=EXCLUDED.kategorie,
                   link_pattern=EXCLUDED.link_pattern,
                   keywords=EXCLUDED.keywords, prio=EXCLUDED.prio, aktiv=TRUE
                 RETURNING id,name,url,prio""",
              (name, url, kategorie, link_pattern, kw, prio))
    return _j(r)


@mcp.tool()
def quelle_schalten(name: str, aktiv: bool) -> str:
    """Quelle an- oder abschalten (z.B. wenn ein Scraper dauerhaft kaputt ist)."""
    r = db.q1("UPDATE quelle SET aktiv=%s WHERE name=%s RETURNING name,aktiv",
              (aktiv, name))
    return _j(r or {"fehler": "keine Quelle mit diesem Namen"})


@mcp.tool()
def regel_anlegen(art: str, muster: str, grund: str = "") -> str:
    """Filterregel anlegen. art: ausschluss | interesse | blocklist.
    muster = Regex, wird auf den Titel angewendet (case-insensitive)."""
    if art not in ("ausschluss", "interesse", "blocklist"):
        return "Fehler: art muss ausschluss, interesse oder blocklist sein"
    r = db.q1("""INSERT INTO regel (art,muster,grund) VALUES (%s,%s,%s)
                 ON CONFLICT (art,muster) DO UPDATE SET aktiv=TRUE,
                 grund=EXCLUDED.grund RETURNING id,art,muster,grund""",
              (art, muster, grund))
    return _j(r)


@mcp.tool()
def regel_loeschen(regel_id: int) -> str:
    """Filterregel deaktivieren."""
    r = db.q1("UPDATE regel SET aktiv=FALSE WHERE id=%s RETURNING id,muster",
              (regel_id,))
    return _j(r or {"fehler": "keine Regel mit dieser id"})


@mcp.tool()
def check_jetzt(quelle: str = "") -> str:
    """Sofortlauf. Ohne Argument alle aktiven Quellen, sonst nur die genannte.
    Dauert je Quelle ein paar Sekunden."""
    return _j(lauf(quelle or None))


@mcp.tool()
def nachricht_an_uwe(text: str) -> str:
    """Telegram-Nachricht an Uwe schicken (HTML erlaubt: <b>, <a href>)."""
    return "verschickt" if notify.telegram(text) else "Telegram nicht erreichbar"


if __name__ == "__main__":
    db.init()
    print(f"MCP auf Port {config.PORT}, Pfad /mcp/<secret>", flush=True)
    mcp.run(transport="streamable-http")
