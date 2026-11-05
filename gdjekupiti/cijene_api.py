"""Klijent za Cijene API (https://cijene.dev).

Svi /v1/ pozivi traže API ključ (Authorization: Bearer <ključ>).
Ključ je besplatan za nekomercijalnu upotrebu.

Odgovori se pretvaraju u jednostavne rječnike; ako API promijeni nazive
polja, popravak ide samo u funkcije _normaliziraj_* ispod.
"""

from __future__ import annotations

import threading
import time

from .mreza import GreskaMreze, dohvati_json, s_parametrima
from .optimizator import Ducan

API = "https://api.cijene.dev"
NAZIVI_LANACA = {
    "konzum": "Konzum", "lidl": "Lidl", "plodine": "Plodine", "spar": "Spar",
    "tommy": "Tommy", "studenac": "Studenac", "kaufland": "Kaufland",
    "eurospin": "Eurospin", "dm": "dm", "ktc": "KTC", "metro": "Metro",
    "trgocentar": "Trgocentar", "zabac": "Žabac", "vrutak": "Vrutak",
    "ribola": "Ribola", "ntl": "NTL", "boso": "Boso", "brodokomerc": "Brodokomerc",
    "lorenco": "Lorenco", "roto": "Roto", "bure": "Bure", "dukat": "Dukat",
}
VELICINA_PAKETA_EAN = 20
TRAJANJE_CACHEA_S = 30 * 60


def naziv_lanca(kod: str) -> str:
    return NAZIVI_LANACA.get((kod or "").lower(), (kod or "?").capitalize())


def _broj(v):
    try:
        if v is None or v == "":
            return None
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _prvi(d: dict, *kljucevi):
    for k in kljucevi:
        if isinstance(d, dict) and d.get(k) not in (None, ""):
            return d[k]
    return None


def _lista(odg, *kljucevi):
    if isinstance(odg, list):
        return odg
    for k in kljucevi:
        if isinstance(odg, dict) and isinstance(odg.get(k), list):
            return odg[k]
    return []


def _normaliziraj_proizvod(p: dict) -> dict | None:
    ean = str(_prvi(p, "ean", "barcode") or "").strip()
    if not ean:
        return None
    lanci = []
    for c in _lista(p.get("chains") or [], "chains"):
        if not isinstance(c, dict):
            continue
        lanci.append({
            "lanac": _prvi(c, "chain", "chain_code", "code") or "",
            "min": _broj(_prvi(c, "min_price", "price", "regular_price")),
            "max": _broj(_prvi(c, "max_price", "price", "regular_price")),
        })
    prvi_lanac = (p.get("chains") or [{}])[0] if isinstance(p.get("chains"), list) and p.get("chains") else {}
    naziv = _prvi(p, "name") or _prvi(prvi_lanac, "name") or ean
    cijene = [x["min"] for x in lanci if x["min"] is not None]
    najjeftiniji = min((x for x in lanci if x["min"] is not None), key=lambda x: x["min"], default=None)
    return {
        "ean": ean,
        "naziv": str(naziv).strip(),
        "marka": str(_prvi(p, "brand") or _prvi(prvi_lanac, "brand") or "").strip(),
        "kolicina": str(_prvi(p, "quantity") or _prvi(prvi_lanac, "quantity") or "").strip(),
        "jedinica": str(_prvi(p, "unit") or _prvi(prvi_lanac, "unit") or "").strip(),
        "cijena_od": min(cijene) if cijene else None,
        "cijena_do": max((x["max"] for x in lanci if x["max"] is not None), default=None),
        "najjeftinije_u": naziv_lanca(najjeftiniji["lanac"]) if najjeftiniji else None,
        "broj_lanaca": len(lanci),
    }


def _normaliziraj_ducan(s: dict, lanac: str | None = None) -> Ducan | None:
    lanac = (lanac or _prvi(s, "chain_code", "chain") or "").lower()
    kod = _prvi(s, "code", "store_id", "id")
    lat, lon = _broj(_prvi(s, "lat", "latitude")), _broj(_prvi(s, "lon", "lng", "longitude"))
    if not lanac or kod is None or lat is None or lon is None:
        return None
    adresa = ", ".join(str(x) for x in (_prvi(s, "address"), _prvi(s, "city")) if x)
    return Ducan(
        kljuc=f"{lanac}:{kod}",
        lanac=lanac,
        naziv=naziv_lanca(lanac),
        adresa=adresa or str(kod),
        lat=lat,
        lon=lon,
    )


def _cijena_iz_zapisa(z: dict) -> float | None:
    """Važeća cijena: akcijska ako postoji i niža, inače redovna."""
    kandidati = [_broj(_prvi(z, k)) for k in ("special_price", "regular_price", "price", "retail_price")]
    kandidati = [c for c in kandidati if c is not None and c > 0]
    return min(kandidati) if kandidati else None


class CijeneAPI:
    def __init__(self, kljuc: str, fetch=dohvati_json, baza: str = API):
        if not kljuc:
            raise ValueError("Nedostaje API ključ za cijene.dev (upiši ga u Postavke)")
        self.kljuc = kljuc
        self.fetch = fetch
        self.baza = baza.rstrip("/")
        self._cache: dict[str, tuple[float, object]] = {}
        self._brava = threading.Lock()

    def _get(self, putanja: str, **parametri):
        url = s_parametrima(f"{self.baza}{putanja}", **parametri)
        with self._brava:
            pogodak = self._cache.get(url)
            if pogodak and time.monotonic() - pogodak[0] < TRAJANJE_CACHEA_S:
                return pogodak[1]
        try:
            odg = self.fetch(url, {"Authorization": f"Bearer {self.kljuc}", "Accept": "application/json"})
        except GreskaMreze as e:
            if "HTTP 401" in str(e) or "HTTP 403" in str(e):
                raise GreskaMreze("cijene.dev ne prihvaća API ključ. Provjeri ga u Postavkama.") from e
            raise
        with self._brava:
            self._cache[url] = (time.monotonic(), odg)
        return odg

    def trazi_proizvode(self, upit: str, limit: int = 30) -> list[dict]:
        odg = self._get("/v1/products/", q=upit)
        rezultati = []
        for p in _lista(odg, "products", "results", "items"):
            n = _normaliziraj_proizvod(p) if isinstance(p, dict) else None
            if n:
                rezultati.append(n)
        return rezultati[:limit]

    def ducani_blizu(self, lat: float, lon: float, d_km: float) -> dict[str, Ducan]:
        odg = self._get("/v1/stores/", lat=f"{lat:.5f}", lon=f"{lon:.5f}", d=f"{d_km:g}")
        ducani = {}
        for s in _lista(odg, "stores", "results"):
            d = _normaliziraj_ducan(s) if isinstance(s, dict) else None
            if d:
                ducani[d.kljuc] = d
        return ducani

    def cijene(self, eanovi: list[str], lat: float, lon: float, d_km: float):
        """Cijene po poslovnicama u krugu d_km: (ducani, {kljuc_ducana: {ean: cijena}})."""
        ducani: dict[str, Ducan] = {}
        cijene: dict[str, dict[str, float]] = {}
        bez_lokacije: list[tuple[str, str, str, float]] = []
        jedinstveni = sorted(set(eanovi))
        for i in range(0, len(jedinstveni), VELICINA_PAKETA_EAN):
            paket = jedinstveni[i:i + VELICINA_PAKETA_EAN]
            odg = self._get("/v1/prices/", eans=",".join(paket),
                            lat=f"{lat:.5f}", lon=f"{lon:.5f}", d=f"{d_km:g}")
            for z in _lista(odg, "store_prices", "prices", "results"):
                if not isinstance(z, dict):
                    continue
                ean = str(_prvi(z, "ean", "barcode") or "")
                cijena = _cijena_iz_zapisa(z)
                trgovina = z.get("store") if isinstance(z.get("store"), dict) else z
                lanac = _prvi(z, "chain", "chain_code") or _prvi(trgovina, "chain_code", "chain")
                if not ean or cijena is None or not lanac:
                    continue
                d = _normaliziraj_ducan(trgovina, lanac)
                if d is None:
                    kod = _prvi(trgovina, "code", "store_id", "id")
                    if kod is not None:
                        bez_lokacije.append((str(lanac).lower(), str(kod), ean, cijena))
                    continue
                ducani[d.kljuc] = d
                cijene.setdefault(d.kljuc, {})[ean] = cijena

        if bez_lokacije:
            # Ako uz cijene nema koordinata, spoji ih s popisom dućana u blizini
            poznati = self.ducani_blizu(lat, lon, d_km)
            for lanac, kod, ean, cijena in bez_lokacije:
                kljuc = f"{lanac}:{kod}"
                if kljuc in poznati:
                    ducani[kljuc] = poznati[kljuc]
                    cijene.setdefault(kljuc, {})[ean] = cijena
        return ducani, cijene
