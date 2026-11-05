"""Adrese (Nominatim / OpenStreetMap) i zračna udaljenost."""

from __future__ import annotations

import math
import threading
import time

from .mreza import dohvati_json, s_parametrima

NOMINATIM = "https://nominatim.openstreetmap.org/search"
_zadnji_upit = 0.0
_brava = threading.Lock()


def zracna_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = f2 - f1
    dl = math.radians(lon2 - lon1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geokodiraj(adresa: str, fetch=dohvati_json) -> list[dict]:
    """Vrati do 5 pogodaka za adresu u Hrvatskoj: [{adresa, lat, lon}]."""
    global _zadnji_upit
    adresa = (adresa or "").strip()
    if len(adresa) < 3:
        return []
    # Nominatim dopušta najviše 1 upit u sekundi
    with _brava:
        cekaj = 1.0 - (time.monotonic() - _zadnji_upit)
        if cekaj > 0:
            time.sleep(cekaj)
        _zadnji_upit = time.monotonic()
    url = s_parametrima(NOMINATIM, q=adresa, format="jsonv2", limit=5,
                        countrycodes="hr", **{"accept-language": "hr"})
    rezultati = fetch(url) or []
    return [
        {"adresa": r.get("display_name", adresa), "lat": float(r["lat"]), "lon": float(r["lon"])}
        for r in rezultati
        if "lat" in r and "lon" in r
    ]
