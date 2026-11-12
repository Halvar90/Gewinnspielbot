import pathlib
from contextlib import contextmanager
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from . import config
from .profil import seed_regeln

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL fehlt")
        _pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=4,
                               kwargs={"row_factory": dict_row}, open=True)
    return _pool


@contextmanager
def cur():
    with pool().connection() as conn:
        with conn.cursor() as c:
            yield c


def q(sql: str, params=None) -> list[dict]:
    with cur() as c:
        c.execute(sql, params or ())
        return c.fetchall() if c.description else []


def q1(sql: str, params=None) -> dict | None:
    rows = q(sql, params)
    return rows[0] if rows else None


# -- Startbestand: Quellen der ersten Version -------------------------------
# link_pattern = Regex auf die URL, keywords = Regex-Teile im Linktext.
SEED_QUELLEN = [
    dict(name="techrush", url="https://techrush.de/category/produkttests",
         kategorie="pc-hardware", link_pattern=r"techrush\.de/\d{4}/|/produkttest",
         keywords=["produkttest", "tester", "testen"], prio=1),
    dict(name="hardwareluxx-lesertests",
         url="https://www.hardwareluxx.de/index.php/news.html",
         kategorie="pc-hardware", link_pattern=r"/news/.+\.html",
         keywords=["lesertest", "testet", "tester gesucht"], prio=2),
    dict(name="gotools-testen",
         url="https://www.gotools.de/werkzeugportal/testen-und-bewerten",
         kategorie="werkzeug", link_pattern=r"gotools\.de/",
         keywords=["test", "bewerten", "gewinn"], prio=3),
    dict(name="gotools-gewinnspiele",
         url="https://www.gotools.de/werkzeugportal/gewinnspiele",
         kategorie="werkzeug", link_pattern=r"gotools\.de/",
         keywords=["gewinn", "verlosung"], prio=4),
    dict(name="mydealz-freebies",
         url="https://www.mydealz.de/rss/gruppe/freebies",
         kategorie="allgemein", link_pattern=None,
         keywords=[], prio=2, methode="rss"),
    dict(name="kostenlos-uebersicht",
         url="https://www.kostenlos.de/gratisartikel-uebersicht",
         kategorie="allgemein", link_pattern=r"kostenlos\.de/",
         keywords=[], prio=4),
    dict(name="supergewinne-technik",
         url="https://www.supergewinne.de/gewinnspiele/technikgewinnspiele",
         kategorie="gewinnspiel", link_pattern=r"/\d{4,6}/",
         keywords=[], prio=4),
    dict(name="brandnooz", url="https://www.brandnooz.de/produkt-test",
         kategorie="lebensmittel", link_pattern=r"brandnooz\.de/produkt-test/",
         keywords=[], prio=3),
    dict(name="hometesterclub",
         url="https://www.hometesterclub.com/de/de/test",
         kategorie="allgemein", link_pattern=r"/de/de/(test|produkt)",
         keywords=[], prio=3),
]


def init():
    """Schema anlegen und Startbestand einspielen. Idempotent."""
    sql = (pathlib.Path(__file__).parent / "schema.sql").read_text()
    with cur() as c:
        c.execute(sql)
        for r in SEED_QUELLEN:
            r = {"methode": "static", **r}
            c.execute("""INSERT INTO quelle
                (name,url,kategorie,link_pattern,keywords,prio,methode)
                VALUES (%(name)s,%(url)s,%(kategorie)s,%(link_pattern)s,
                        %(keywords)s,%(prio)s,%(methode)s)
                ON CONFLICT (name) DO NOTHING""", r)
        for art, muster, grund in seed_regeln():
            c.execute("""INSERT INTO regel (art,muster,grund)
                         VALUES (%s,%s,%s) ON CONFLICT DO NOTHING""",
                      (art, muster, grund))
    return "Schema und Startbestand bereit"
