"""Udaljenosti i rute preko besplatnih OSRM servera (FOSSGIS, OpenStreetMap).

Ako servis nije dostupan, koristi se procjena: zračna linija × 1,3 i
prosječna brzina za odabrani način puta.
"""

from __future__ import annotations

from .geo import zracna_km
from .mreza import GreskaMreze, dohvati_json
from .optimizator import Matrica

OSRM = "https://routing.openstreetmap.de"
PROFILI = {"auto": "routed-car", "bicikl": "routed-bike", "pjesice": "routed-foot"}
BRZINA_KMH = {"auto": 30.0, "bicikl": 15.0, "pjesice": 5.0}  # za procjenu
FAKTOR_ZAOBILAZENJA = 1.3


def _koordinate(tocke) -> str:
    return ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in tocke)


def procjena_matrice(nacin: str, start, ducani) -> Matrica:
    tocke = [start] + [(d.lat, d.lon) for d in ducani]
    km = [[zracna_km(*a, *b) * FAKTOR_ZAOBILAZENJA for b in tocke] for a in tocke]
    v = BRZINA_KMH[nacin]
    sati = [[d / v for d in red] for red in km]
    return Matrica(["start"] + [d.kljuc for d in ducani], km, sati, procjena=True)


def matrica(nacin: str, start, ducani, fetch=dohvati_json) -> Matrica:
    """Matrica stvarnih udaljenosti; za nedostupne parove koristi procjenu."""
    gruba = procjena_matrice(nacin, start, ducani)
    if not ducani:
        return gruba
    tocke = [start] + [(d.lat, d.lon) for d in ducani]
    url = f"{OSRM}/{PROFILI[nacin]}/table/v1/driving/{_koordinate(tocke)}?annotations=duration,distance"
    try:
        odg = fetch(url, timeout=25)
    except GreskaMreze:
        return gruba
    if odg.get("code") != "Ok" or "distances" not in odg or "durations" not in odg:
        return gruba
    km, sati = [], []
    for i, red in enumerate(odg["distances"]):
        km_red, h_red = [], []
        for j, metara in enumerate(red):
            sekundi = odg["durations"][i][j]
            if metara is None or sekundi is None:
                km_red.append(gruba.km[i][j])
                h_red.append(gruba.sati[i][j])
            else:
                km_red.append(metara / 1000.0)
                h_red.append(sekundi / 3600.0)
        km.append(km_red)
        sati.append(h_red)
    return Matrica(gruba.kljucevi, km, sati, procjena=False)


def geometrija(nacin: str, tocke, fetch=dohvati_json) -> dict:
    """Linija rute za kartu: {"tocke": [[lat, lon], ...], "procjena": bool}."""
    if len(tocke) < 2:
        return {"tocke": [list(t) for t in tocke], "procjena": True}
    url = (f"{OSRM}/{PROFILI[nacin]}/route/v1/driving/{_koordinate(tocke)}"
           "?overview=full&geometries=geojson")
    try:
        odg = fetch(url, timeout=25)
        koord = odg["routes"][0]["geometry"]["coordinates"]
        return {"tocke": [[lat, lon] for lon, lat in koord], "procjena": False}
    except (GreskaMreze, KeyError, IndexError, TypeError):
        return {"tocke": [list(t) for t in tocke], "procjena": True}
