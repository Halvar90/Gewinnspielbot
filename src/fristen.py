"""Taegliche Erinnerung: Einsendeschluesse und Adventskalender-Tuerchen.

Aufruf: python -m src.fristen
"""
import datetime as dt
from . import db, notify


def faellig(vorlauf: int = 3) -> dict:
    heute = dt.date.today()
    grenze = heute + dt.timedelta(days=vorlauf)
    tuerchen = db.q("""SELECT * FROM frist WHERE aktiv AND taeglich
                       AND faellig >= %s
                       AND (erledigt_am IS NULL OR erledigt_am < %s)
                       ORDER BY titel""", (heute, heute))
    einmalig = db.q("""SELECT * FROM frist WHERE aktiv AND NOT taeglich
                       AND erledigt_am IS NULL AND faellig <= %s
                       ORDER BY faellig""", (grenze,))
    offen = db.q("""SELECT id,titel,url,frist FROM fund
                    WHERE status IN ('gemeldet','wartet_auf_uwe')
                    AND frist IS NOT NULL AND frist <= %s
                    ORDER BY frist""", (grenze,))
    return dict(tuerchen=tuerchen, einmalig=einmalig, funde=offen)


def erinnere() -> str:
    d = faellig()
    if not any(d.values()):
        return "nichts faellig"
    teile = []
    if d["tuerchen"]:
        teile.append("<b>Heute wieder dran</b>\n" + "\n".join(
            f"• <a href=\"{t['url']}\">{t['titel']}</a>" if t["url"]
            else f"• {t['titel']}" for t in d["tuerchen"]))
    if d["einmalig"]:
        teile.append("<b>Frist laeuft ab</b>\n" + "\n".join(
            f"• {t['titel']} – bis {t['faellig']}"
            + (f"\n  {t['url']}" if t["url"] else "") for t in d["einmalig"]))
    if d["funde"]:
        teile.append("<b>Offene Funde mit Frist</b>\n" + "\n".join(
            f"• {f['titel'][:80]} – bis {f['frist']}\n  {f['url']}"
            for f in d["funde"]))
    txt = "\n\n".join(teile)
    notify.telegram(txt)
    return txt


if __name__ == "__main__":
    db.init()
    print(erinnere())
