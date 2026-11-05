"""Cijena goriva s HAK-ove stranice (podaci Ministarstva gospodarstva, mzoe-gor.hr).

HAK za svaku tvrtku i vrstu goriva objavljuje najnižu, najvišu i medijan cijenu.
Za izračun uzimamo cijenu koju ima najviše tvrtki (to je u pravilu
cijena osnovnog goriva koju ograničava Vlada).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from html.parser import HTMLParser

from .mreza import dohvati

HAK_URL = "https://www.hak.hr/info/cijene-goriva/"
VRSTE = {"benzin": "Eurosuper 95", "dizel": "Eurodizel", "lpg": "Autoplin (LPG)"}


def _bez_kvacica(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def vrsta_goriva(naziv: str) -> str | None:
    n = _bez_kvacica(naziv)
    if any(x in n for x in ("boc", "loz", "ulje", "plav")):
        return None
    if any(x in n for x in ("autoplin", "lpg", "unp")):
        return "lpg"
    if "dizel" in n or "diesel" in n:
        return "dizel"
    if "100" in n:
        return "benzin100"
    if "95" in n or "super" in n:
        return "benzin"
    return None


def euro(tekst: str) -> float | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)", tekst.replace("\xa0", " "))
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


class _Tablice(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.redovi: list[list[str]] = []
        self.tekst: list[str] = []
        self._red: list[str] | None = None
        self._celija: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._red = []
        elif tag in ("td", "th") and self._red is not None:
            self._celija = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._red is not None and self._celija is not None:
            self._red.append(" ".join("".join(self._celija).split()))
            self._celija = None
        elif tag == "tr" and self._red is not None:
            self.redovi.append(self._red)
            self._red = None

    def handle_data(self, data):
        self.tekst.append(data)
        if self._celija is not None:
            self._celija.append(data)


def parsiraj_hak(html: str) -> dict:
    p = _Tablice()
    p.feed(html)
    medijani: dict[str, list[float]] = {}
    for red in p.redovi:
        if len(red) < 5:
            continue
        vrsta = vrsta_goriva(red[1])
        medijan = euro(red[4])
        if vrsta is None or medijan is None or not (0.3 < medijan < 5):
            continue
        medijani.setdefault(vrsta, []).append(medijan)
    if not medijani:
        raise ValueError("Na HAK-ovoj stranici nisam našao tablicu s cijenama goriva")

    cijene = {}
    for vrsta, lista in medijani.items():
        brojac = Counter(round(x, 3) for x in lista)
        najcesce = max(brojac.values())
        cijene[vrsta] = min(c for c, n in brojac.items() if n == najcesce)

    datum = None
    m = re.search(r"Zadnje a.urirano:\s*(\d{1,2}\.\d{1,2}\.\d{4})", " ".join(p.tekst))
    if m:
        datum = m.group(1)
    return {"cijene": cijene, "datum": datum, "izvor": "HAK / mzoe-gor.hr"}


def dohvati_cijene_goriva(fetch=dohvati) -> dict:
    html = fetch(HAK_URL).decode("utf-8", "replace")
    return parsiraj_hak(html)
