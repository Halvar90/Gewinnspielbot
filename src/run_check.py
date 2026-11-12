"""Cron-Lauf: alle aktiven Quellen pruefen, Neues melden.

Aufruf:  python -m src.run_check          (alle aktiven Quellen)
         python -m src.run_check techrush (nur eine)

Beim ersten Lauf des Tages (vor 8 Uhr UTC) geht zusaetzlich die
Fristen-Erinnerung raus - so braucht es keinen zweiten Cron-Dienst.
"""
import datetime as dt
import sys
import time
import traceback

from . import db, notify
from .filter import pruefe, regeln
from .scrape.base import detail, sammle


def lauf(nur: str | None = None) -> dict:
    db.init()
    start = time.time()
    rg = regeln()
    wo = "AND name = %s" if nur else ""
    quellen = db.q(f"SELECT * FROM quelle WHERE aktiv {wo} ORDER BY prio",
                   (nur,) if nur else None)
    neu, gesehen, fehler, details = [], 0, 0, []
    detail_budget = 15  # Requests fuer Detailseiten pro Lauf

    for qu in quellen:
        try:
            funde = sammle(qu)
            gesehen += len(funde)
            durch = 0
            # Schon bekannte Funde gar nicht weiter anfassen
            bekannt = {r["url_hash"] for r in db.q(
                "SELECT url_hash FROM fund WHERE url_hash = ANY(%s)",
                ([f.url_hash for f in funde] or [""],))}
            for f in funde:
                if f.url_hash in bekannt:
                    continue
                u = pruefe(f, qu, rg)
                # Bei wichtigen Quellen die Detailseite nachladen: dort
                # stehen Frist und ob die Runde noch laeuft.
                if u.durch and detail_budget > 0 and (qu.get("prio") or 5) <= 3:
                    detail_budget -= 1
                    frist, zu = detail(f.url)
                    if frist:
                        f.frist = frist
                    if zu:
                        u = u.__class__(False, f"Runde beendet ({zu})", u.prio)
                    elif frist and frist < dt.date.today().isoformat():
                        u = u.__class__(False, f"Frist abgelaufen ({frist})", u.prio)
                row = db.q1("""
                    INSERT INTO fund (url_hash,url,titel,quelle,kategorie,
                                      frist,status,vorfilter)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (url_hash) DO NOTHING
                    RETURNING id,titel,url,quelle,frist,vorfilter""",
                    (f.url_hash, f.url, f.titel, f.quelle, f.kategorie,
                     f.frist, "neu" if u.durch else "verworfen", u.grund))
                if row and u.durch:
                    row["prio"] = u.prio
                    neu.append(row)
                    durch += 1
            # Null Treffer ist kein Absturz, aber oft trotzdem ein Defekt
            # (Seite umgebaut, Cloudflare, JavaScript). Mitzaehlen.
            if funde:
                db.q("""UPDATE quelle SET letzter_lauf=now(),
                        letzter_fehler=NULL, fehler_serie=0
                        WHERE name=%s""", (qu["name"],))
            else:
                db.q("""UPDATE quelle SET letzter_lauf=now(),
                        letzter_fehler='0 Treffer - Seite pruefen',
                        fehler_serie=fehler_serie+1 WHERE name=%s""",
                     (qu["name"],))
            details.append(f"{qu['name']}: {len(funde)} gesehen, {durch} neu")
        except Exception as e:
            fehler += 1
            msg = f"{type(e).__name__}: {e}"[:400]
            db.q("""UPDATE quelle SET letzter_lauf=now(), letzter_fehler=%s,
                    fehler_serie=fehler_serie+1 WHERE name=%s""",
                 (msg, qu["name"]))
            details.append(f"{qu['name']}: FEHLER {msg}")
            traceback.print_exc()

    gemeldet = melde(neu)
    db.q("""INSERT INTO lauf (dauer_s,quellen,gesehen,neu,gemeldet,fehler,details)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
         (round(time.time() - start, 1), len(quellen), gesehen, len(neu),
          gemeldet, fehler, "\n".join(details)))
    # Quellen, die dreimal hintereinander versagt haben, einmal melden
    kaputt = db.q("SELECT name,letzter_fehler FROM quelle WHERE fehler_serie=3")
    if kaputt:
        notify.telegram("⚠️ Quelle liefert nichts mehr:\n" + "\n".join(
            f"<code>{k['name']}</code>: {k['letzter_fehler'] or ''}"[:200]
            for k in kaputt))
    return dict(quellen=len(quellen), gesehen=gesehen, neu=len(neu),
                gemeldet=gemeldet, fehler=fehler, details=details)


def melde(neu: list[dict]) -> int:
    """Push nur fuer echte Treffer. Alles mit "unklar" bleibt auf Status
    'neu' liegen und wird von Claude ueber MCP durchgesehen - sonst
    erschlaegt der aufgestaute Bestand jeden Lauf per Telegram."""
    if not neu:
        return 0
    treffer = [f for f in neu if (f.get("vorfilter") or "").startswith("passt")]
    rest = len(neu) - len(treffer)
    if not treffer:
        if rest:
            print(f"[melde] {rest} unklare Funde liegen zur Triage", flush=True)
        return 0
    treffer.sort(key=lambda f: (f.get("prio") or 5, f["quelle"]))
    txt = (f"<b>{len(treffer)} neue Treffer</b>\n\n"
           + "\n\n".join(notify.zeile(f) for f in treffer[:20]))
    if len(treffer) > 20:
        txt += f"\n\n... und {len(treffer) - 20} weitere."
    if rest:
        txt += f"\n\nDazu {rest} unklare Funde - Claude sieht sie durch."
    if notify.telegram(txt):
        db.q("""UPDATE fund SET status='gemeldet', geaendert=now()
                WHERE id = ANY(%s) AND status='neu'""",
             ([f["id"] for f in treffer],))
        return len(treffer)
    return 0


if __name__ == "__main__":
    nur = sys.argv[1] if len(sys.argv) > 1 else None
    r = lauf(nur)
    print(r, flush=True)
    if not nur and dt.datetime.now(dt.timezone.utc).hour < 8:
        from .fristen import erinnere
        print("Fristen:", erinnere()[:300], flush=True)
