import html
import httpx
from . import config

API = "https://api.telegram.org/bot{}/sendMessage"


def telegram(text: str) -> bool:
    if not (config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID):
        print("[notify] Telegram nicht konfiguriert:\n" + text)
        return False
    for teil in _stuecke(text, 3800):
        try:
            r = httpx.post(API.format(config.TELEGRAM_TOKEN),
                           json={"chat_id": config.TELEGRAM_CHAT_ID,
                                 "text": teil, "parse_mode": "HTML",
                                 "disable_web_page_preview": True},
                           timeout=20.0)
            if r.status_code != 200:
                print("[notify] Fehler", r.status_code, r.text[:200])
                return False
        except Exception as e:  # Benachrichtigung darf den Lauf nie killen
            print("[notify] Ausnahme", e)
            return False
    return True


def _stuecke(text: str, n: int):
    zeilen, puffer = text.split("\n"), ""
    for z in zeilen:
        if len(puffer) + len(z) + 1 > n:
            yield puffer
            puffer = ""
        puffer += z + "\n"
    if puffer.strip():
        yield puffer


def zeile(f: dict) -> str:
    eilig = "⏰ " if (f.get("prio") or 5) <= 1 else ""
    frist = f" <i>(bis {f['frist']})</i>" if f.get("frist") else ""
    return (f"{eilig}<a href=\"{html.escape(f['url'], quote=True)}\">"
            f"{html.escape(f['titel'][:110])}</a>{frist}\n"
            f"   <code>{html.escape(f['quelle'])}</code> – "
            f"{html.escape(f.get('vorfilter') or '')}")
