"""Povezuje izvore podataka, pohranu i izračun."""

from __future__ import annotations

import datetime as dt
import threading

from . import geo, gorivo, rute
from .cijene_api import CijeneAPI
from .demo import DemoIzvor, demo_adrese, demo_gorivo
from .mreza import GreskaMreze
from .optimizator import NACINI, Artikl, ParametriPuta, optimiziraj, rangiraj_kandidate, zaokruzi
from .pohrana import Pohrana

PRETPOSTAVLJENA_CIJENA_GORIVA = {"benzin": 1.70, "dizel": 1.90, "lpg": 1.10}
MAX_DUCANA_ZA_RUTE = 40  # OSRM tablica s 41 točkom je i dalje brza


class GreskaKorisnika(Exception):
    """Greška koju korisnik može sam popraviti (poruka ide u sučelje)."""


class Servis:
    def __init__(self, pohrana: Pohrana, demo: bool = False):
        self.pohrana = pohrana
        self.demo = demo
        self._izvor = None
        self._kljuc_izvora = None
        self._brava = threading.Lock()

    # Izvori
    def izvor(self):
        if self.demo:
            if self._izvor is None:
                self._izvor = DemoIzvor()
            return self._izvor
        kljuc = self.pohrana.postavke().get("api_kljuc", "").strip()
        if not kljuc:
            raise GreskaKorisnika("Upiši API ključ za cijene.dev u Postavkama (ili pokreni demo način).")
        with self._brava:
            if self._izvor is None or self._kljuc_izvora != kljuc:
                self._izvor = CijeneAPI(kljuc)
                self._kljuc_izvora = kljuc
            return self._izvor

    def trazi_proizvode(self, upit: str) -> list[dict]:
        upit = (upit or "").strip()
        if len(upit) < 2:
            return []
        return self.izvor().trazi_proizvode(upit)

    def adrese(self, upit: str) -> list[dict]:
        if self.demo:
            return demo_adrese(upit)
        return geo.geokodiraj(upit)

    # Gorivo
    def gorivo(self, osvjezi: bool = False) -> dict:
        if self.demo:
            return {**demo_gorivo(), "dohvaceno": dt.date.today().isoformat()}
        danas = dt.date.today().isoformat()
        spremljeno = self.pohrana.gorivo_cache()
        if spremljeno and spremljeno.get("dohvaceno") == danas and not osvjezi:
            return spremljeno
        try:
            novo = {**gorivo.dohvati_cijene_goriva(), "dohvaceno": danas}
            self.pohrana.spremi_gorivo_cache(novo)
            return novo
        except (GreskaMreze, ValueError) as e:
            if spremljeno:
                return {**spremljeno, "greska": f"Nisam uspio osvježiti: {e}"}
            return {"cijene": {}, "datum": None, "izvor": None, "greska": str(e)}

    def cijena_goriva(self, postavke: dict) -> tuple[float, str]:
        g = postavke["gorivo"]
        vrsta = g.get("vrsta", "benzin")
        if g.get("rucna_cijena"):
            return float(g["rucna_cijena"]), "ručno upisana"
        podaci = self.gorivo()
        c = podaci.get("cijene", {}).get(vrsta)
        if c:
            return float(c), f"{podaci.get('izvor')} {podaci.get('datum') or ''}".strip()
        return PRETPOSTAVLJENA_CIJENA_GORIVA.get(vrsta, 1.70), "pretpostavka (dohvat nije uspio)"

    # Izračun
    def _artikli(self) -> list[Artikl]:
        artikli = []
        for s in self.pohrana.popis():
            eanovi = [str(e) for e in s.get("eanovi", []) if e]
            if not eanovi:
                continue
            artikli.append(Artikl(
                id=str(s.get("id")),
                naziv=s.get("naziv") or eanovi[0],
                kolicina=max(1, int(s.get("kolicina") or 1)),
                eanovi=eanovi,
            ))
        return artikli

    def izracunaj(self, nacin: str, polaziste: dict | None = None) -> dict:
        if nacin not in NACINI:
            raise GreskaKorisnika("Odaberi način puta: auto, pješice ili bicikl.")
        postavke = self.pohrana.postavke()
        artikli = self._artikli()
        if not artikli:
            raise GreskaKorisnika("Popis za kupovinu je prazan. Dodaj barem jedan artikl.")

        start = polaziste if polaziste and polaziste.get("lat") is not None else postavke["dom"]
        if start.get("lat") is None or start.get("lon") is None:
            raise GreskaKorisnika("Upiši polazište ili kućnu adresu u Postavkama.")
        lat, lon = float(start["lat"]), float(start["lon"])

        max_km = float(postavke["max_km"].get(nacin, 5))
        eanovi = sorted({e for a in artikli for e in a.eanovi})
        ducani, cijene = self.izvor().cijene(eanovi, lat, lon, max_km)

        iskljuceni = {x.lower() for x in postavke.get("iskljuceni_lanci", [])}
        ducani = {k: d for k, d in ducani.items() if d.lanac not in iskljuceni}

        kandidati = rangiraj_kandidate(artikli, list(ducani), cijene, limit=MAX_DUCANA_ZA_RUTE)
        lista = [ducani[k] for k in kandidati]
        if self.demo:
            matrica = rute.procjena_matrice(nacin, (lat, lon), lista)
        else:
            matrica = rute.matrica(nacin, (lat, lon), lista)

        cijena_goriva, izvor_goriva = self.cijena_goriva(postavke)
        p = ParametriPuta(
            nacin=nacin,
            potrosnja_l_100km=float(postavke["gorivo"].get("potrosnja") or 0),
            cijena_goriva=cijena_goriva,
            vrijednost_sata=float(postavke.get("vrijednost_sata") or 0),
            racunaj_vrijeme=bool(postavke.get("racunaj_vrijeme_auto")),
            max_km=max_km,
            max_ducana=max(1, min(3, int(postavke.get("max_ducana") or 3))),
        )
        r = zaokruzi(optimiziraj(artikli, {k: ducani[k] for k in kandidati}, cijene, matrica, p))
        r.update({
            "nacin": nacin,
            "polaziste": {"lat": lat, "lon": lon, "adresa": start.get("adresa", "")},
            "parametri": {
                "max_km": max_km,
                "cijena_goriva": cijena_goriva if nacin == "auto" else None,
                "izvor_goriva": izvor_goriva if nacin == "auto" else None,
                "potrosnja": p.potrosnja_l_100km if nacin == "auto" else None,
                "vrijednost_sata": p.vrijednost_sata,
                "racuna_vrijeme": nacin != "auto" or p.racunaj_vrijeme,
            },
            "broj_artikala": len(artikli),
            "demo": self.demo,
        })
        return r

    def ruta(self, nacin: str, tocke: list) -> dict:
        if nacin not in NACINI:
            raise GreskaKorisnika("Nepoznat način puta.")
        tocke = [(float(t[0]), float(t[1])) for t in tocke][:12]
        if self.demo:
            return {"tocke": [list(t) for t in tocke], "procjena": True}
        return rute.geometrija(nacin, tocke)
