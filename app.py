"""Gdje kupiti? Lokalna web aplikacija za najisplativiju kupovinu.

Pokretanje:
    python app.py            -> otvori http://127.0.0.1:8765 u pregledniku
    python app.py --demo     -> izmišljeni podaci, bez API ključa i interneta
    python app.py --lan      -> dostupno i s mobitela na kućnoj mreži
    python app.py --provjeri -> provjeri vezu sa svim vanjskim servisima
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import socket
import sys
import threading
import traceback
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from gdjekupiti.mreza import GreskaMreze
from gdjekupiti.pohrana import Pohrana
from gdjekupiti.servis import GreskaKorisnika, Servis

KORIJEN = Path(__file__).resolve().parent
STATIC = KORIJEN / "static"
DOZVOLJENE_POSTAVKE = {
    "api_kljuc", "dom", "gorivo", "vrijednost_sata", "racunaj_vrijeme_auto",
    "max_km", "max_ducana", "iskljuceni_lanci", "zadnji_nacin",
}
MAX_TIJELO = 1_000_000


def javne_postavke(p: dict) -> dict:
    """Postavke za sučelje, bez API ključa."""
    javno = {k: v for k, v in p.items() if k != "api_kljuc"}
    javno["api_kljuc_postavljen"] = bool(p.get("api_kljuc"))
    return javno


def ocisti_popis(popis) -> list:
    if not isinstance(popis, list):
        raise GreskaKorisnika("Popis mora biti lista.")
    cisto = []
    for s in popis[:200]:
        if not isinstance(s, dict):
            continue
        eanovi = [str(e)[:32] for e in (s.get("eanovi") or []) if e][:50]
        if not eanovi:
            continue
        try:
            kolicina = int(s.get("kolicina") or 1)
        except (TypeError, ValueError):
            kolicina = 1
        cisto.append({
            "id": str(s.get("id") or eanovi[0])[:64],
            "naziv": str(s.get("naziv") or "")[:200],
            "kolicina": max(1, min(99, kolicina)),
            "tip": "grupa" if s.get("tip") == "grupa" else "tocno",
            "eanovi": eanovi,
            "proizvodi": s.get("proizvodi", [])[:50] if isinstance(s.get("proizvodi"), list) else [],
        })
    return cisto


def napravi_handler(servis: Servis):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GdjeKupiti/0.1"

        def log_message(self, fmt, *args):  # tiši ispis u konzoli
            if "/api/" in (args[0] if args else ""):
                sys.stderr.write("  " + (fmt % args) + "\n")

        # Pomoćne
        def _json(self, podaci, status=HTTPStatus.OK):
            tijelo = json.dumps(podaci, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(tijelo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(tijelo)

        def _greska(self, poruka, status=HTTPStatus.BAD_REQUEST):
            self._json({"greska": poruka}, status)

        def _tijelo(self):
            duljina = int(self.headers.get("Content-Length") or 0)
            if duljina > MAX_TIJELO:
                raise GreskaKorisnika("Zahtjev je prevelik.")
            if not duljina:
                return {}
            try:
                return json.loads(self.rfile.read(duljina).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                raise GreskaKorisnika("Neispravan JSON.")

        def _staticno(self, putanja):
            if putanja in ("", "/"):
                putanja = "/index.html"
            datoteka = (STATIC / putanja.lstrip("/")).resolve()
            if STATIC not in datoteka.parents or not datoteka.is_file():
                self._greska("Nema takve stranice", HTTPStatus.NOT_FOUND)
                return
            sadrzaj = datoteka.read_bytes()
            vrsta = mimetypes.guess_type(datoteka.name)[0] or "application/octet-stream"
            if vrsta.startswith("text/") or vrsta in ("application/javascript", "image/svg+xml"):
                vrsta += "; charset=utf-8"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", vrsta)
            self.send_header("Content-Length", str(len(sadrzaj)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(sadrzaj)

        def _obradi(self, metoda):
            url = urlsplit(self.path)
            if not url.path.startswith("/api/"):
                if metoda == "GET":
                    return self._staticno(url.path)
                return self._greska("Nepoznata putanja", HTTPStatus.NOT_FOUND)
            # Zaštita od tuđih stranica: izmjene traže naše zaglavlje
            if metoda != "GET" and self.headers.get("X-Gdje-Kupiti") != "1":
                return self._greska("Zabranjeno", HTTPStatus.FORBIDDEN)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                return self._api(metoda, url.path, q)
            except GreskaKorisnika as e:
                return self._greska(str(e))
            except GreskaMreze as e:
                return self._greska(str(e), HTTPStatus.BAD_GATEWAY)
            except Exception as e:  # neočekivano: ispiši u konzolu, korisniku kratka poruka
                traceback.print_exc()
                return self._greska(f"Neočekivana greška: {e}", HTTPStatus.INTERNAL_SERVER_ERROR)

        def _api(self, metoda, putanja, q):
            p = servis.pohrana
            if putanja == "/api/stanje" and metoda == "GET":
                post = p.postavke()
                return self._json({
                    "demo": servis.demo,
                    "ima_kljuc": bool(post.get("api_kljuc")) or servis.demo,
                    "ima_dom": post["dom"].get("lat") is not None,
                    "postavke": javne_postavke(post),
                })
            if putanja == "/api/postavke":
                if metoda == "GET":
                    return self._json(javne_postavke(p.postavke()))
                if metoda == "PUT":
                    tijelo = self._tijelo()
                    promjene = {k: v for k, v in tijelo.items() if k in DOZVOLJENE_POSTAVKE}
                    if "api_kljuc" in promjene:
                        promjene["api_kljuc"] = str(promjene["api_kljuc"] or "").strip()
                    return self._json(javne_postavke(p.spremi_postavke(promjene)))
            if putanja == "/api/popis":
                if metoda == "GET":
                    return self._json(p.popis())
                if metoda == "PUT":
                    return self._json(p.spremi_popis(ocisti_popis(self._tijelo())))
            if putanja == "/api/grupe":
                if metoda == "GET":
                    return self._json(p.grupe())
                if metoda == "PUT":
                    grupe = self._tijelo()
                    if not isinstance(grupe, dict):
                        raise GreskaKorisnika("Grupe moraju biti objekt.")
                    return self._json(p.spremi_grupe(grupe))
            if putanja == "/api/proizvodi" and metoda == "GET":
                return self._json(servis.trazi_proizvode(q.get("q", "")))
            if putanja == "/api/adresa" and metoda == "GET":
                return self._json(servis.adrese(q.get("q", "")))
            if putanja == "/api/gorivo" and metoda == "GET":
                return self._json(servis.gorivo(osvjezi=q.get("osvjezi") == "1"))
            if putanja == "/api/izracun" and metoda == "POST":
                t = self._tijelo()
                return self._json(servis.izracunaj(t.get("nacin", "auto"), t.get("polaziste")))
            if putanja == "/api/ruta" and metoda == "POST":
                t = self._tijelo()
                return self._json(servis.ruta(t.get("nacin", "auto"), t.get("tocke") or []))
            return self._greska("Nepoznata API putanja", HTTPStatus.NOT_FOUND)

        def do_GET(self):
            self._obradi("GET")

        def do_PUT(self):
            self._obradi("PUT")

        def do_POST(self):
            self._obradi("POST")

    return Handler


def lokalna_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def provjeri(servis: Servis):
    """Provjeri sve vanjske servise i ispiši što radi, a što ne."""
    from gdjekupiti import geo, gorivo, rute
    from gdjekupiti.optimizator import Ducan

    def korak(naziv, fn):
        try:
            rez = fn()
            print(f"[ OK ] {naziv}: {rez}")
            return True
        except Exception as e:
            print(f"[GREŠKA] {naziv}: {e}")
            return False

    print("Provjera vanjskih servisa\n")
    korak("Adrese (Nominatim)", lambda: geo.geokodiraj("Trg bana Josipa Jelačića, Zagreb")[0]["adresa"][:60])
    korak("Cijene goriva (HAK)", lambda: gorivo.dohvati_cijene_goriva()["cijene"])
    d = Ducan("x", "konzum", "Konzum", "", 45.8100, 15.9700)
    korak("Rute (OSRM, auto)",
          lambda: f"{rute.matrica('auto', (45.8131, 15.9772), [d]).km[0][1]:.2f} km do testne točke")
    kljuc = servis.pohrana.postavke().get("api_kljuc")
    if not kljuc:
        print("[PRESKOČENO] cijene.dev: API ključ nije upisan u Postavkama")
        return
    api = servis.izvor()
    prvi = {}

    def proizvodi():
        sirovo = api._get("/v1/products/", q="mlijeko")
        print("        sirovi odgovor (početak):", json.dumps(sirovo, ensure_ascii=False)[:400])
        r = api.trazi_proizvode("mlijeko")
        prvi["ean"] = r[0]["ean"]
        return f"{len(r)} proizvoda, prvi: {r[0]['naziv']} ({r[0]['ean']})"

    if korak("cijene.dev pretraga", proizvodi):
        def cijene():
            sirovo = api._get("/v1/prices/", eans=prvi["ean"], lat="45.81310", lon="15.97720", d="3")
            print("        sirovi odgovor (početak):", json.dumps(sirovo, ensure_ascii=False)[:400])
            ducani, c = api.cijene([prvi["ean"]], 45.8131, 15.9772, 3)
            return f"{len(ducani)} dućana u krugu 3 km od centra Zagreba"
        korak("cijene.dev cijene po dućanima", cijene)


def main():
    parser = argparse.ArgumentParser(description="Gdje kupiti? Najisplativija kupovina.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--demo", action="store_true", help="izmišljeni podaci za isprobavanje")
    parser.add_argument("--lan", action="store_true", help="dopusti pristup s drugih uređaja na mreži")
    parser.add_argument("--bez-preglednika", action="store_true", help="ne otvaraj preglednik")
    parser.add_argument("--provjeri", action="store_true", help="provjeri vanjske servise i izađi")
    parser.add_argument("--podaci", default=str(KORIJEN / "data"), help="mapa za postavke i popis")
    args = parser.parse_args()

    mapa = Path(args.podaci) / ("demo" if args.demo else "")
    servis = Servis(Pohrana(mapa), demo=args.demo)
    if args.provjeri:
        provjeri(servis)
        return

    adresa = "0.0.0.0" if args.lan else "127.0.0.1"
    try:
        server = ThreadingHTTPServer((adresa, args.port), napravi_handler(servis))
    except OSError:
        print(f"Port {args.port} je zauzet. Je li aplikacija već pokrenuta? Probaj --port 8766")
        sys.exit(1)

    url = f"http://127.0.0.1:{args.port}"
    print("Gdje kupiti? je pokrenut" + (" (DEMO podaci)" if args.demo else ""))
    print(f"  Na ovom računalu: {url}")
    if args.lan:
        print(f"  S mobitela na istoj mreži: http://{lokalna_ip()}:{args.port}")
    print("  Za gašenje zatvori ovaj prozor ili pritisni Ctrl+C\n")
    if not args.bez_preglednika:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nUgašeno.")


if __name__ == "__main__":
    main()
