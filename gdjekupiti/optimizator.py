"""Izračun najisplativije kupovine.

Ukupni trošak opcije = cijena artikala + trošak puta.
Trošak puta = gorivo (samo auto) + vrijeme (pješice/bicikl uvijek, auto ako je uključeno).

Modul ne zna ništa o internetu: dobiva dućane, cijene i matricu udaljenosti,
pa ga je lako testirati i mijenjati.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations, permutations

NACINI = ("auto", "pjesice", "bicikl")
MAX_KANDIDATA = 20  # koliko dućana ulazi u kombinacije (20 -> do 1350 kombinacija od 3)


@dataclass
class Artikl:
    id: str
    naziv: str
    kolicina: int
    eanovi: list[str]  # jedan EAN = "točno ovaj", više = "bilo koji takav"


@dataclass
class Ducan:
    kljuc: str
    lanac: str
    naziv: str
    adresa: str
    lat: float
    lon: float


@dataclass
class Matrica:
    """Udaljenosti (km) i trajanja (h) između točaka. Indeks 0 je polazište."""

    kljucevi: list[str]
    km: list[list[float]]
    sati: list[list[float]]
    procjena: bool = False  # True ako nisu stvarne rute nego zračna linija
    _indeks: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._indeks = {k: i for i, k in enumerate(self.kljucevi)}

    def i(self, kljuc: str) -> int:
        return self._indeks[kljuc]


@dataclass
class ParametriPuta:
    nacin: str
    potrosnja_l_100km: float
    cijena_goriva: float
    vrijednost_sata: float
    racunaj_vrijeme: bool  # za auto: uračunaj i vrijeme
    max_km: float  # najveća udaljenost dućana od polazišta (u jednom smjeru)
    max_ducana: int = 3

    def trosak_puta(self, km: float, sati: float) -> tuple[float, float]:
        gorivo = 0.0
        if self.nacin == "auto":
            gorivo = km * self.potrosnja_l_100km / 100.0 * self.cijena_goriva
        vrijeme = 0.0
        if self.nacin != "auto" or self.racunaj_vrijeme:
            vrijeme = sati * self.vrijednost_sata
        return gorivo, vrijeme


def cijena_artikla(artikl: Artikl, cijene_ducana: dict[str, float]):
    """Najjeftinija prihvaćena varijanta u dućanu: (ukupno, ean, jedinična) ili None."""
    najbolja = None
    for ean in artikl.eanovi:
        c = cijene_ducana.get(ean)
        if c is None:
            continue
        if najbolja is None or c < najbolja[2]:
            najbolja = (c * artikl.kolicina, ean, c)
    return najbolja


def rangiraj_kandidate(artikli, kljucevi_ducana, cijene, limit=MAX_KANDIDATA):
    """Odabere dućane koji imaju smisla za kombiniranje.

    Uzima dućane s najboljom pokrivenošću i cijenom košarice, plus za svaki
    artikl dućan u kojem je najjeftiniji (inače bi podjela mogla promašiti).
    """
    ocjene = []
    for k in kljucevi_ducana:
        cd = cijene.get(k, {})
        iznos, nedostaje = 0.0, 0
        for a in artikli:
            c = cijena_artikla(a, cd)
            if c is None:
                nedostaje += 1
            else:
                iznos += c[0]
        ocjene.append((nedostaje, iznos, k))
    ocjene.sort()
    odabrani = [k for _, _, k in ocjene[: max(1, limit // 2)]]

    for a in artikli:
        najbolji = None
        for k in kljucevi_ducana:
            c = cijena_artikla(a, cijene.get(k, {}))
            if c is not None and (najbolji is None or c[0] < najbolji[0]):
                najbolji = (c[0], k)
        if najbolji and najbolji[1] not in odabrani:
            odabrani.append(najbolji[1])

    for _, _, k in ocjene:
        if len(odabrani) >= limit:
            break
        if k not in odabrani:
            odabrani.append(k)
    return odabrani[:limit]


def _najbolja_tura(podskup, m: Matrica, p: ParametriPuta):
    najbolja = None
    for redoslijed in permutations(podskup):
        tocke = [0] + [m.i(k) for k in redoslijed] + [0]
        km = sum(m.km[a][b] for a, b in zip(tocke, tocke[1:]))
        sati = sum(m.sati[a][b] for a, b in zip(tocke, tocke[1:]))
        gorivo, vrijeme = p.trosak_puta(km, sati)
        trosak = gorivo + vrijeme
        if najbolja is None or (trosak, km) < (najbolja[0], najbolja[2]):
            najbolja = (trosak, list(redoslijed), km, sati, gorivo, vrijeme)
    return najbolja


def _ocijeni_podskup(podskup, artikli, ducani, cijene, m, p):
    po_ducanu = {k: [] for k in podskup}
    nedostaje = []
    iznos_artikala = 0.0
    for a in artikli:
        najbolji = None
        for k in podskup:
            c = cijena_artikla(a, cijene.get(k, {}))
            if c is not None and (najbolji is None or c[0] < najbolji[0][0]):
                najbolji = (c, k)
        if najbolji is None:
            nedostaje.append(a.naziv)
            continue
        (ukupno, ean, jedinicna), k = najbolji
        iznos_artikala += ukupno
        po_ducanu[k].append({
            "id": a.id, "naziv": a.naziv, "kolicina": a.kolicina,
            "ean": ean, "jedinicna": round(jedinicna, 2), "cijena": round(ukupno, 2),
        })

    if len(podskup) > 1 and any(not v for v in po_ducanu.values()):
        return None  # dućan u koji ne bi ništa kupio nema smisla posjetiti

    trosak, redoslijed, km, sati, gorivo, vrijeme = _najbolja_tura(podskup, m, p)
    ukupno = iznos_artikala + trosak
    return {
        "ducani": [
            {
                "kljuc": k,
                "lanac": ducani[k].lanac,
                "naziv": ducani[k].naziv,
                "adresa": ducani[k].adresa,
                "lat": ducani[k].lat,
                "lon": ducani[k].lon,
                "km_od_starta": round(m.km[0][m.i(k)], 2),
                "artikli": po_ducanu[k],
                "iznos": round(sum(x["cijena"] for x in po_ducanu[k]), 2),
            }
            for k in redoslijed
        ],
        "artikli_iznos": iznos_artikala,
        "km": km,
        "minuta": sati * 60.0,
        "trosak_goriva": gorivo,
        "trosak_vremena": vrijeme,
        "trosak_puta": trosak,
        "ukupno": ukupno,
        "nedostaje": nedostaje,
        "_rang": (len(nedostaje), round(ukupno, 6), len(podskup), km),
    }


def optimiziraj(artikli, ducani, cijene, m: Matrica, p: ParametriPuta, top_n: int = 6):
    if p.nacin not in NACINI:
        raise ValueError(f"Nepoznat način puta: {p.nacin}")

    u_dometu = [
        k for k in m.kljucevi[1:]
        if k in ducani and m.km[0][m.i(k)] <= p.max_km
    ]
    rezultat = {
        "najbolja": None,
        "najbolji_jedan": None,
        "opcije": [],
        "usteda_vs_jedan": 0.0,
        "nedostupno_svugdje": [],
        "broj_ducana_u_dometu": len(u_dometu),
        "procjena_udaljenosti": m.procjena,
    }
    if not u_dometu or not artikli:
        return rezultat

    rezultat["nedostupno_svugdje"] = [
        a.naziv for a in artikli
        if all(cijena_artikla(a, cijene.get(k, {})) is None for k in u_dometu)
    ]

    kandidati = rangiraj_kandidate(artikli, u_dometu, cijene)
    opcije = []
    for velicina in range(1, max(1, p.max_ducana) + 1):
        for podskup in combinations(kandidati, velicina):
            o = _ocijeni_podskup(podskup, artikli, ducani, cijene, m, p)
            if o is not None:
                opcije.append(o)

    opcije.sort(key=lambda o: o["_rang"])
    jedan = [o for o in opcije if len(o["ducani"]) == 1]

    najbolja = opcije[0]
    najbolji_jedan = jedan[0] if jedan else None

    # Prikaži najbolje opcije, ali uvijek i najbolji pojedinačni dućan
    prikaz = opcije[:top_n]
    if najbolji_jedan is not None and najbolji_jedan not in prikaz:
        prikaz.append(najbolji_jedan)

    rezultat["najbolja"] = najbolja
    rezultat["najbolji_jedan"] = najbolji_jedan
    rezultat["opcije"] = prikaz
    if najbolji_jedan is not None and len(najbolji_jedan["nedostaje"]) == len(najbolja["nedostaje"]):
        rezultat["usteda_vs_jedan"] = najbolji_jedan["ukupno"] - najbolja["ukupno"]
    for o in opcije:
        o.pop("_rang", None)
    return rezultat


def zaokruzi(rezultat):
    """Zaokruži iznose za prikaz (izračun koristi pune vrijednosti)."""
    def z(o):
        if not o:
            return o
        for k in ("artikli_iznos", "trosak_goriva", "trosak_vremena", "trosak_puta", "ukupno"):
            o[k] = round(o[k], 2)
        o["km"] = round(o["km"], 2)
        o["minuta"] = round(o["minuta"])
        return o

    vidjeni = set()
    for o in [rezultat.get("najbolja"), rezultat.get("najbolji_jedan"), *rezultat.get("opcije", [])]:
        if o is not None and id(o) not in vidjeni:
            vidjeni.add(id(o))
            z(o)
    rezultat["usteda_vs_jedan"] = round(rezultat.get("usteda_vs_jedan", 0.0), 2)
    return rezultat
