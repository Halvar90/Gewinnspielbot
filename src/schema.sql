-- Quellen: deklarativ, neue Quellen brauchen keinen Code
CREATE TABLE IF NOT EXISTS quelle (
  id            SERIAL PRIMARY KEY,
  name          TEXT UNIQUE NOT NULL,
  url           TEXT NOT NULL,
  kategorie     TEXT NOT NULL DEFAULT 'allgemein',
  link_pattern  TEXT,              -- Regex: welche Links der Seite sind Angebote
  keywords      TEXT[] DEFAULT '{}',-- Linktext muss eines davon enthalten (leer = alle)
  methode       TEXT NOT NULL DEFAULT 'static',  -- static | json
  prio          INT  NOT NULL DEFAULT 5,         -- 1 = eilig (z.B. techrush 11 Uhr)
  aktiv         BOOLEAN NOT NULL DEFAULT TRUE,
  letzter_lauf  TIMESTAMPTZ,
  letzter_fehler TEXT,
  fehler_serie  INT NOT NULL DEFAULT 0,
  angelegt      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Funde: ein Eintrag pro Angebot, dedupliziert ueber url_hash
CREATE TABLE IF NOT EXISTS fund (
  id         SERIAL PRIMARY KEY,
  url_hash   TEXT UNIQUE NOT NULL,
  url        TEXT NOT NULL,
  titel      TEXT NOT NULL,
  quelle     TEXT NOT NULL,
  kategorie  TEXT,
  frist      DATE,
  status     TEXT NOT NULL DEFAULT 'neu',
    -- neu | gemeldet | beworben | wartet_auf_uwe | verworfen | gewonnen | erledigt
  bewertung  TEXT,            -- Claudes Einschaetzung
  notiz      TEXT,
  vorfilter  TEXT,            -- warum der Vorfilter es durchgelassen/geblockt hat
  gefunden   TIMESTAMPTZ NOT NULL DEFAULT now(),
  geaendert  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_status_idx ON fund (status, gefunden DESC);

-- Fristen: Adventskalender-Tuerchen, Suchbilder, Einsendeschluesse
CREATE TABLE IF NOT EXISTS frist (
  id        SERIAL PRIMARY KEY,
  titel     TEXT NOT NULL,
  url       TEXT,
  faellig   DATE NOT NULL,
  taeglich  BOOLEAN NOT NULL DEFAULT FALSE,  -- taeglich bis faellig (Tuerchen)
  erledigt_am DATE,                          -- bei taeglich: letzter erledigter Tag
  notiz     TEXT,
  aktiv     BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS frist_faellig_idx ON frist (aktiv, faellig);

-- Profilregeln: Ausschluesse und Interessen, von Claude pflegbar
CREATE TABLE IF NOT EXISTS regel (
  id      SERIAL PRIMARY KEY,
  art     TEXT NOT NULL,          -- ausschluss | interesse | blocklist
  muster  TEXT NOT NULL,          -- Regex, case-insensitive
  grund   TEXT,
  aktiv   BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE (art, muster)
);

-- Lauf-Protokoll
CREATE TABLE IF NOT EXISTS lauf (
  id        SERIAL PRIMARY KEY,
  gestartet TIMESTAMPTZ NOT NULL DEFAULT now(),
  dauer_s   NUMERIC,
  quellen   INT DEFAULT 0,
  gesehen   INT DEFAULT 0,
  neu       INT DEFAULT 0,
  gemeldet  INT DEFAULT 0,
  fehler    INT DEFAULT 0,
  details   TEXT
);
