"""Uwes Filterregeln als Startbestand. Spaeter ueber MCP pflegbar (Tabelle `regel`)."""

# Harte Ausschluesse: Treffer wird verworfen
AUSSCHLUSS = [
    (r"shampoo|haarpflege|haarshampoo|haarserum|haarfarbe|conditioner|spuelung",
     "Glatze"),
    (r"kaffee|espresso|kaffeevollautomat|kaffeepad|kaffeekapsel|barista",
     "trinkt keinen Kaffee"),
    (r"damen|frauen|lippenstift|mascara|wimpern|nagellack|tampon|binden|"
     r"damenhygiene|damenmode|damenduft|intimpflege|bh\b|menstruation",
     "nur fuer Frauen"),
    (r"baby|windel|babynahrung|schwanger|kinderwagen|stillen|babybrei",
     "kein Baby"),
    (r"nassfutter|katzenfutter nass|dosenfutter|frischbeutel|schale.*katze",
     "Katzen nur Trockenfutter"),
    (r"dinner for cats|dinner for dogs", "Telefon-Verkaufsanruf"),
    (r"kassenbon|cashback|geld.?zurueck|geld.?zuruck|kauf nachweis|"
     r"code eingeben|aktionscode vom produkt",
     "Kauf noetig - macht Uwe selbst"),
    (r"crabstone|burda direct", "Lead-Gewinnspiel mit Sponsorenliste"),
    (r"\btelegram\b.*tester|amazon.?tester", "keine Telegram-Testergruppen"),
]

# Interessen: Treffer wird hochpriorisiert
INTERESSE = [
    (r"grafikkarte|gpu|geforce|radeon|rtx|cpu|prozessor|mainboard|ssd|nvme|"
     r"ram|arbeitsspeicher|netzteil|gehaeuse|cpu.?kuehler|wasserkuehlung|"
     r"monitor|tastatur|\bmaus\b|headset|pc.?hardware|gaming.?pc|notebook",
     "PC-Hardware - Schwerpunkt"),
    (r"akkuschrauber|bohrmaschine|werkzeug|werkstatt|saege|schleifer|"
     r"bosch professional|makita|einhell|multitool|akku.?werkzeug",
     "Werkzeug"),
    (r"heissluftfritteuse|airfryer|fritteuse", "nutzt er taeglich"),
    (r"trockenfutter|katzenstreu|katzen.?spielzeug|kratzbaum", "2 Katzen"),
    (r"motorroller|\broller\b|\bvespa\b|motorrad|\bquad\b|wohnmobil|"
     r"wohnwagen|\bauto\b|kfz|werkstattwagen",
     "Kfz-Interesse"),
    (r"bargeld|\d{3,}\s?(?:euro|eur|€)|gutschein|goldbarren|reise|"
     r"urlaub|kreuzfahrt",
     "Bargeld/Reisen"),
    (r"lesertest|produkttester gesucht|testpilot|tester gesucht|"
     r"testen und behalten|testpaket",
     "Testaktion"),
    (r"big.?and.?tall|uebergroesse|grosse groessen|tall.?size",
     "204 cm - nur Tall"),
]

# Treffer-Stichwoerter: ohne eines davon ist es wahrscheinlich kein Angebot
RELEVANT = [
    r"gewinnspiel", r"verlosung", r"gewinne", r"zu gewinnen", r"gratis",
    r"kostenlos", r"gratisprobe", r"probe", r"muster", r"produkttest",
    r"produkttester", r"lesertest", r"testpilot", r"tester", r"testen",
    r"freebie", r"umsonst", r"geschenkt", r"adventskalender", r"gewinnt",
]

# Was bereits erledigt ist und nicht erneut kommen soll (1x pro Haushalt)
ERLEDIGT = [
    (r"platinum", "Probe 2026 bereits bestellt"),
    (r"josera", "Probe 10.11.2026 bestellt"),
]


def seed_regeln():
    """Liefert Zeilen fuer die Tabelle `regel`."""
    rows = []
    for muster, grund in AUSSCHLUSS:
        rows.append(("ausschluss", muster, grund))
    for muster, grund in INTERESSE:
        rows.append(("interesse", muster, grund))
    for muster, grund in ERLEDIGT:
        rows.append(("ausschluss", muster, grund))
    return rows
