"""Demo podaci: izmišljeni dućani i cijene za isprobavanje bez API ključa.

Dućani se postave oko polazišta, a cijene su izmišljene (ali stalne),
pa se cijela aplikacija može isprobati bez interneta.
"""

from __future__ import annotations

import hashlib
import math

from .cijene_api import naziv_lanca
from .geo import zracna_km
from .optimizator import Ducan

# (naziv, marka, količina, jedinica, osnovna cijena)
PROIZVODI = [
    ("Svježe mlijeko 2,8% m.m.", "Marka A", "1", "L", 1.29),
    ("Svježe mlijeko 2,8% m.m.", "Marka B", "1", "L", 1.19),
    ("Svježe mlijeko 3,2% m.m.", "Marka C", "1", "L", 1.39),
    ("Trajno mlijeko 2,8% m.m.", "Marka A", "1", "L", 1.09),
    ("Kruh polubijeli", "Pekara D", "600", "g", 1.49),
    ("Kruh integralni", "Pekara D", "500", "g", 1.89),
    ("Jaja L", "Farma E", "10", "kom", 2.99),
    ("Jaja M", "Farma F", "10", "kom", 2.59),
    ("Maslac", "Marka A", "250", "g", 3.49),
    ("Jogurt tekući", "Marka B", "1", "kg", 1.59),
    ("Sir gouda narezani", "Marka G", "400", "g", 4.49),
    ("Pileća prsa file", "Farma H", "1", "kg", 8.99),
    ("Mljevena junetina", "Farma H", "500", "g", 5.49),
    ("Tjestenina špageti", "Marka I", "500", "g", 1.19),
    ("Riža dugo zrno", "Marka I", "1", "kg", 2.29),
    ("Brašno T-550", "Mlin J", "1", "kg", 0.99),
    ("Šećer kristal", "Marka K", "1", "kg", 1.19),
    ("Ulje suncokretovo", "Marka K", "1", "L", 2.19),
    ("Kava mljevena", "Marka L", "250", "g", 4.29),
    ("Banane", "", "1", "kg", 1.49),
    ("Jabuke", "", "1", "kg", 1.29),
    ("Krumpir", "", "2", "kg", 1.99),
    ("Toaletni papir 3-slojni", "Marka M", "10", "kom", 4.99),
    ("Deterdžent za suđe", "Marka N", "750", "ml", 1.89),
]

# (lanac, razina cijena, udaljenost km, smjer u stupnjevima)
DUCANI = [
    ("konzum", 1.08, 0.6, 20), ("lidl", 0.92, 1.4, 110), ("spar", 1.05, 1.0, 250),
    ("kaufland", 0.95, 2.6, 320), ("plodine", 0.98, 2.1, 190), ("studenac", 1.10, 0.4, 290),
    ("konzum", 1.06, 2.9, 150), ("eurospin", 0.90, 3.8, 60), ("tommy", 1.03, 4.5, 230),
    ("lidl", 0.92, 5.5, 10),
]


def ean(i: int) -> str:
    return f"0000000{i:06d}"


def _hash01(*dijelovi) -> float:
    h = hashlib.sha256("|".join(map(str, dijelovi)).encode()).digest()
    return int.from_bytes(h[:4], "big") / 2**32


def _pomak(lat, lon, km, smjer):
    dlat = km * math.cos(math.radians(smjer)) / 111.32
    dlon = km * math.sin(math.radians(smjer)) / (111.32 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


class DemoIzvor:
    demo = True

    def trazi_proizvode(self, upit: str, limit: int = 30) -> list[dict]:
        rijeci = [r for r in (upit or "").lower().split() if r]
        rezultati = []
        for i, (naziv, marka, kol, jed, osnovna) in enumerate(PROIZVODI):
            tekst = f"{naziv} {marka}".lower()
            if rijeci and all(r in tekst for r in rijeci):
                po_lancu = {}
                for l, r, _, _ in DUCANI:
                    c = self._cijena(l, r, i)
                    if c is not None:
                        po_lancu[l] = min(c, po_lancu.get(l, c))
                if not po_lancu:
                    continue
                najjeftiniji = min(po_lancu, key=po_lancu.get)
                rezultati.append({
                    "ean": ean(i), "naziv": naziv, "marka": marka, "kolicina": kol,
                    "jedinica": jed, "cijena_od": po_lancu[najjeftiniji],
                    "cijena_do": max(po_lancu.values()),
                    "najjeftinije_u": naziv_lanca(najjeftiniji), "broj_lanaca": len(po_lancu),
                })
        return rezultati[:limit]

    def _cijena(self, lanac, razina, i):
        if _hash01(lanac, i, "ima") < 0.1:
            return None  # ponekad dućan nema proizvod
        osnovna = PROIZVODI[i][4]
        sum_ = 0.9 + 0.2 * _hash01(lanac, i)
        return round(osnovna * razina * sum_, 2)

    def cijene(self, eanovi, lat, lon, d_km):
        ducani, cijene = {}, {}
        indeksi = {ean(i): i for i in range(len(PROIZVODI))}
        for br, (lanac, razina, km, smjer) in enumerate(DUCANI):
            dlat, dlon = _pomak(lat, lon, km, smjer)
            if zracna_km(lat, lon, dlat, dlon) > d_km:
                continue
            kljuc = f"{lanac}:demo{br + 1}"
            ducani[kljuc] = Ducan(kljuc, lanac, naziv_lanca(lanac),
                                  f"Demo lokacija {br + 1}", dlat, dlon)
            for e in eanovi:
                if e in indeksi:
                    c = self._cijena(lanac, razina, indeksi[e])
                    if c is not None:
                        cijene.setdefault(kljuc, {})[e] = c
        return ducani, cijene


def demo_gorivo() -> dict:
    return {"cijene": {"benzin": 1.69, "dizel": 1.89, "lpg": 1.09}, "datum": None,
            "izvor": "demo"}


def demo_adrese(upit: str) -> list[dict]:
    return [{"adresa": f"{upit} (demo: centar Zagreba)", "lat": 45.8131, "lon": 15.9772}]
