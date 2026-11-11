# gratis-scout

Sammelt Gratisproben, Produkttests und Gewinnspiele, filtert nach Uwes
Profil und meldet Neues per Telegram. Steuerbar von Claude aus ueber einen
MCP-Connector.

## Aufteilung
- **Bot** (dieses Repo): sammeln, entdoppeln, regelbasiert vorfiltern, melden.
  Kein Sprachmodell, keine API-Kosten.
- **Claude** ueber MCP: bewerten, Bewerbungstexte, neue Quellen und Regeln
  eintragen, Status pflegen.
- **Uwe**: anhaken und absenden. Der Bot nimmt nirgends selbst teil.

## Aufbau
```
src/config.py       Umgebungsvariablen
src/profil.py       Uwes Ausschluesse und Interessen (Startbestand)
src/schema.sql      Tabellen: quelle, fund, frist, regel, lauf
src/db.py           Verbindung + Startbestand (9 Quellen)
src/scrape/base.py  generischer Scraper (Links statt CSS-Selektoren)
src/filter.py       Vorfilter
src/notify.py       Telegram
src/run_check.py    Cron-Lauf
src/fristen.py      taegliche Erinnerung
src/mcp_server.py   MCP-Server, 15 Tools
```

Quellen stehen in der Datenbank, nicht im Code. Eine neue Quelle braucht
keinen Commit, nur einen `quelle_anlegen`-Aufruf.

## Railway einrichten
1. Neues Projekt → **Deploy from GitHub repo** → dieses Repo.
2. **+ New → Database → Postgres** ins gleiche Projekt. `DATABASE_URL`
   setzt Railway dann selbst.
3. Variablen im Service setzen:
   `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `MCP_SECRET` (lange Zufallsfolge).
4. **Settings → Networking → Generate Domain**. Connector-URL ist dann
   `https://<domain>/mcp/<MCP_SECRET>`.
5. **Settings → Serverless (App Sleeping)** einschalten: der MCP-Server
   schlaeft, bis Claude ihn anspricht. Spart den Grossteil der Kosten.
6. Zwei **Cron-Services** im gleichen Projekt, gleiches Repo. Start Command
   im Service setzen (railway.json setzt absichtlich keinen):
   - `python -m src.run_check`, Schedule `0 6,10,18 * * *`
   - `python -m src.fristen`, Schedule `30 7 * * *`
   Beide brauchen dieselben Variablen (Railway: Variable References).
7. **Usage Limit** im Konto setzen, damit nichts entgleist.

## In Claude einrichten
Einstellungen → Connectors → Add custom connector → Connector-URL von
oben eintragen. Kein OAuth noetig, der geheime Pfad ist die Anmeldung.

## Lokal testen
```
export DATABASE_URL=... TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=...
pip install -r requirements.txt
python -m src.run_check techrush   # eine Quelle
python -m src.run_check            # alle
```

## Bekannte Grenzen
- Nur statisches HTML. Seiten, die ihre Inhalte per JavaScript nachladen
  (REWE, kjero), brauchen Playwright - absichtlich nicht in v1.
- Captchas und Cloudflare stoppen den Bot. Solche Quellen bleiben manuell.
- Der Scraper sammelt breit und filtert danach. Lieber ein paar Fehlfunde
  als ein verpasster Lesertest.
