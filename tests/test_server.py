import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import app
from gdjekupiti.demo import ean
from gdjekupiti.pohrana import Pohrana
from gdjekupiti.servis import Servis


class TestServerDemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        servis = Servis(Pohrana(cls.tmp.name), demo=True)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.napravi_handler(servis))
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.tmp.cleanup()

    def zahtjev(self, metoda, putanja, tijelo=None, zaglavlje=True):
        podaci = json.dumps(tijelo).encode() if tijelo is not None else None
        req = urllib.request.Request(self.url + putanja, data=podaci, method=metoda)
        req.add_header("Content-Type", "application/json")
        if zaglavlje:
            req.add_header("X-Gdje-Kupiti", "1")
        try:
            with urllib.request.urlopen(req) as odg:
                return odg.status, json.loads(odg.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_cijeli_tok(self):
        s, stanje = self.zahtjev("GET", "/api/stanje")
        self.assertEqual(s, 200)
        self.assertTrue(stanje["demo"])

        s, post = self.zahtjev("PUT", "/api/postavke", {
            "dom": {"adresa": "Test", "lat": 45.8131, "lon": 15.9772},
            "api_kljuc": "tajno", "nepoznato": 1,
        })
        self.assertEqual(s, 200)
        self.assertNotIn("api_kljuc", post)
        self.assertTrue(post["api_kljuc_postavljen"])
        self.assertNotIn("nepoznato", post)

        s, proizvodi = self.zahtjev("GET", "/api/proizvodi?q=mlijeko")
        self.assertEqual(s, 200)
        self.assertGreaterEqual(len(proizvodi), 3)

        popis = [
            {"id": "m", "naziv": "Mlijeko", "kolicina": 2, "tip": "grupa",
             "eanovi": [ean(0), ean(1), ean(2)]},
            {"id": "k", "naziv": "Kruh", "kolicina": 1, "tip": "tocno", "eanovi": [ean(4)]},
            {"id": "j", "naziv": "Jaja", "kolicina": "x", "tip": "tocno", "eanovi": [ean(6)]},
        ]
        s, spremljeno = self.zahtjev("PUT", "/api/popis", popis)
        self.assertEqual(s, 200)
        self.assertEqual(spremljeno[2]["kolicina"], 1)

        for nacin in ("auto", "pjesice", "bicikl"):
            s, r = self.zahtjev("POST", "/api/izracun", {"nacin": nacin})
            self.assertEqual(s, 200, r)
            self.assertIsNotNone(r["najbolja"], nacin)
            self.assertLessEqual(r["najbolja"]["ukupno"], r["najbolji_jedan"]["ukupno"])
            for d in r["najbolja"]["ducani"]:
                self.assertLessEqual(d["km_od_starta"], r["parametri"]["max_km"])

        s, ruta = self.zahtjev("POST", "/api/ruta",
                               {"nacin": "auto", "tocke": [[45.81, 15.97], [45.82, 15.98]]})
        self.assertEqual(s, 200)
        self.assertEqual(len(ruta["tocke"]), 2)

    def test_izmjena_bez_zaglavlja_je_zabranjena(self):
        s, _ = self.zahtjev("PUT", "/api/popis", [], zaglavlje=False)
        self.assertEqual(s, 403)

    def test_prazan_popis_daje_poruku(self):
        self.zahtjev("PUT", "/api/popis", [])
        s, r = self.zahtjev("POST", "/api/izracun", {"nacin": "auto"})
        self.assertEqual(s, 400)
        self.assertIn("prazan", r["greska"])

    def test_staticne_datoteke(self):
        with urllib.request.urlopen(self.url + "/") as odg:
            self.assertIn(b"Gdje kupiti", odg.read())
        s, _ = self.zahtjev("GET", "/../app.py")
        self.assertEqual(s, 404)


if __name__ == "__main__":
    unittest.main()
