"""Spremanje postavki, popisa i grupa u JSON datoteke u mapi data/."""

from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

ZADANE_POSTAVKE = {
    "api_kljuc": "",
    "dom": {"adresa": "", "lat": None, "lon": None},
    "gorivo": {"vrsta": "benzin", "potrosnja": 6.5, "rucna_cijena": None},
    "vrijednost_sata": 6.0,
    "racunaj_vrijeme_auto": False,
    "max_km": {"auto": 10.0, "bicikl": 5.0, "pjesice": 2.0},
    "max_ducana": 3,
    "iskljuceni_lanci": [],
    "zadnji_nacin": "auto",
}


def _spoji(baza: dict, novo: dict) -> dict:
    rez = copy.deepcopy(baza)
    for k, v in (novo or {}).items():
        if isinstance(v, dict) and isinstance(rez.get(k), dict):
            rez[k] = _spoji(rez[k], v)
        else:
            rez[k] = v
    return rez


class Pohrana:
    def __init__(self, mapa: Path):
        self.mapa = Path(mapa)
        self.mapa.mkdir(parents=True, exist_ok=True)
        self._brava = threading.Lock()

    def _citaj(self, ime: str, zadano):
        put = self.mapa / ime
        if not put.exists():
            return copy.deepcopy(zadano)
        try:
            return json.loads(put.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Oštećena datoteka: sačuvaj je sa strane i kreni ispočetka
            put.replace(put.with_suffix(".ostecena.json"))
            return copy.deepcopy(zadano)

    def _pisi(self, ime: str, podaci):
        put = self.mapa / ime
        privremena = put.with_suffix(".tmp")
        privremena.write_text(json.dumps(podaci, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(privremena, put)

    # Postavke
    def postavke(self) -> dict:
        with self._brava:
            return _spoji(ZADANE_POSTAVKE, self._citaj("postavke.json", {}))

    def spremi_postavke(self, promjene: dict) -> dict:
        with self._brava:
            nove = _spoji(_spoji(ZADANE_POSTAVKE, self._citaj("postavke.json", {})), promjene)
            self._pisi("postavke.json", nove)
            return nove

    # Popis za kupovinu
    def popis(self) -> list:
        with self._brava:
            return self._citaj("popis.json", [])

    def spremi_popis(self, popis: list) -> list:
        with self._brava:
            self._pisi("popis.json", popis)
            return popis

    # Zapamćene grupe "bilo koji takav"
    def grupe(self) -> dict:
        with self._brava:
            return self._citaj("grupe.json", {})

    def spremi_grupe(self, grupe: dict) -> dict:
        with self._brava:
            self._pisi("grupe.json", grupe)
            return grupe

    # Zadnja poznata cijena goriva
    def gorivo_cache(self) -> dict | None:
        with self._brava:
            return self._citaj("gorivo.json", None)

    def spremi_gorivo_cache(self, podaci: dict):
        with self._brava:
            self._pisi("gorivo.json", podaci)
