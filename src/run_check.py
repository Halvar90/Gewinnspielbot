"""Cron-Lauf: alle aktiven Quellen pruefen, Neues melden.

Aufruf:  python -m src.run_check          (alle aktiven Quellen)
         python -m src.run_check techrush (nur eine)
"""
import sys
import time
import traceback

from . import db, notify
from .filter import pruefe, regeln
from .scrape.base import sammle


def lauf(nur: str | None = None) -> dict:
    db.init()
    start = time.time()
    rg = regeln()
    wo = "AND name = %s" if nur else ""
    quellen = db.q(f"SELECT * FROM quelle WHERE aktiv {wo} ORDER BY prio",
                   (nur,) if nur else None)
    neu, gesehen, fehler, details = [], 0, 0, []

    for qu in quellen:
        try:
            funde = sammle(qu)
            gesehen += len(funde)
            durch = 0
            for f in funde:
                u = pruefe(f, qu, rg)
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
            db.q("""UPDATE quelle SET letzter_lauf=now(), letzter_fehler=NULL,
                    fehler_serie=0 WHERE name=%s""", (qu["name"],))
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
    if not neu:
        return 0
    neu.sort(key=lambda f: (f.get("prio") or 5, f["quelle"]))
    txt = (f"<b>{len(neu)} neue Funde</b>\n\n"
           + "\n\n".join(notify.zeile(f) for f in neu[:25]))
    if len(neu) > 25:
        txt += f"\n\n… und {len(neu) - 25} weitere, siehe Dashboard."
    if notify.telegram(txt):
        ids = [f["id"] for f in neu]
        db.q("""UPDATE fund SET status='gemeldet', geaendert=now()
                WHERE id = ANY(%s) AND status='neu'""", (ids,))
        return len(neu)
    return 0


if __name__ == "__main__":
    r = lauf(sys.argv[1] if len(sys.argv) > 1 else None)
    print(r)
