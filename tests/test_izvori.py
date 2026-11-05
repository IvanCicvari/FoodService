import json
import unittest

from gdjekupiti import gorivo, rute
from gdjekupiti.cijene_api import CijeneAPI
from gdjekupiti.mreza import GreskaMreze
from gdjekupiti.optimizator import Ducan


def tablica(redovi):
    tr = "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in redovi
    )
    return ("<table><thead><tr><th>Obveznik</th><th>Gorivo</th><th>Minimalna</th>"
            f"<th>Maksimalna</th><th>Medijan</th></tr></thead><tbody>{tr}</tbody></table>")


HAK_HTML = (
    "<html><body><p>Izvor podataka: www.mzoe-gor.hr | Zadnje ažurirano: 05.11.2026</p>"
    + tablica([
        ["<strong>Adria Oil d.o.o.</strong>", "EUROSUPER 95", "1,64 €", "1,69 €", "1,69 €"],
        ["Adria Oil d.o.o.", "EUROSUPER 95 G-POWER", "1,84 €", "1,84 €", "1,84 €"],
        ["INA", "EUROSUPER 95 CLASS PLUS", "1,69 €", "1,76 €", "1,69 €"],
        ["LUKOIL", "Eurosuper BS 95 ECTO", "1,69 €", "2,04 €", "1,85 €"],
        ["Tifon", "EVO Eurosuper 95 BS", "1,69 €", "1,76 €", "1,69 €"],
    ])
    + tablica([
        ["Coral", "Shell V-Power EuroSuper 100", "1,85 €", "2,30 €", "2,30 €"],
    ])
    + tablica([
        ["Adria Oil", "EURODIESEL G-POWER", "1,46 €", "2,15 €", "2,15 €"],
        ["Adria Oil", "EURODIESEL", "1,72 €", "1,89 €", "1,89 €"],
        ["INA", "EURODIZEL CLASS PLUS", "1,89 €", "2,02 €", "1,89 €"],
        ["Petrol", "Q MAX EURODIZEL B7", "1,89 €", "2,40 €", "2,17 €"],
    ])
    + tablica([
        ["Adria Oil", "AUTOPLIN", "1,01 €", "1,14 €", "1,08 €"],
        ["INA", "AUTOPLIN", "1,09 €", "1,13 €", "1,09 €"],
        ["LUKOIL", "AUTOPLIN (UNP)", "1,04 €", "1,13 €", "1,06 €"],
        ["Petrol", "Q MAX AUTOPLIN", "1,01 €", "1,13 €", "1,09 €"],
    ])
    + tablica([["INA", "EURODIZEL PLAVI", "1,45 €", "1,45 €", "1,45 €"]])
    + tablica([["Petrol", "LOŽ ULJE", "1,66 €", "1,66 €", "1,66 €"]])
    + tablica([["Coral", "PLIN U BOCI - UNP 10 KG", "24,50 €", "24,50 €", "24,50 €"]])
    + "</body></html>"
)


class TestGorivo(unittest.TestCase):
    def test_parsira_najcescu_cijenu_po_vrsti(self):
        r = gorivo.parsiraj_hak(HAK_HTML)
        self.assertEqual(r["cijene"]["benzin"], 1.69)
        self.assertEqual(r["cijene"]["dizel"], 1.89)
        self.assertEqual(r["cijene"]["lpg"], 1.09)
        self.assertEqual(r["cijene"]["benzin100"], 2.30)
        self.assertEqual(r["datum"], "05.11.2026")

    def test_plavi_dizel_i_boce_se_ne_racunaju(self):
        self.assertIsNone(gorivo.vrsta_goriva("Eurodiesel BS PLAVI"))
        self.assertIsNone(gorivo.vrsta_goriva("UNP - U BOCI OD 10 KG"))
        self.assertIsNone(gorivo.vrsta_goriva("EURO LOŽIVO ULJE EL"))
        self.assertEqual(gorivo.vrsta_goriva("Shell Fuelsave EuroDiesel"), "dizel")

    def test_bez_tablice_javlja_gresku(self):
        with self.assertRaises(ValueError):
            gorivo.parsiraj_hak("<html><body>Nema ničega</body></html>")


class LazniFetch:
    """Vraća unaprijed pripremljene odgovore prema putanji URL-a."""

    def __init__(self, odgovori):
        self.odgovori = odgovori
        self.pozivi = []

    def __call__(self, url, zaglavlja=None, timeout=None):
        self.pozivi.append((url, zaglavlja))
        for putanja, odg in self.odgovori.items():
            if putanja in url:
                if isinstance(odg, Exception):
                    raise odg
                return json.loads(json.dumps(odg))
        raise AssertionError(f"Neočekivan URL {url}")


TRGOVINA_KONZUM = {"chain_code": "konzum", "code": "PJ50", "type": "supermarket",
                   "address": "Ilica 10", "city": "Zagreb", "zipcode": "10000",
                   "lat": 45.8130, "lon": 15.9700}


class TestCijeneAPI(unittest.TestCase):
    def test_trazi_proizvode_normalizira_i_salje_kljuc(self):
        f = LazniFetch({"/v1/products/": {"products": [{
            "ean": "3850108020154", "brand": "Dukat", "name": "Svježe mlijeko 2,8%",
            "quantity": "1", "unit": "L",
            "chains": [
                {"chain": "konzum", "name": "DUKAT MLIJEKO", "min_price": "1.39", "max_price": "1.49"},
                {"chain": "lidl", "name": "Mlijeko", "min_price": 1.29, "max_price": 1.29},
            ],
        }]}})
        api = CijeneAPI("tajna", fetch=f)
        r = api.trazi_proizvode("mlijeko")
        self.assertEqual(r[0]["ean"], "3850108020154")
        self.assertEqual(r[0]["cijena_od"], 1.29)
        self.assertEqual(r[0]["najjeftinije_u"], "Lidl")
        self.assertEqual(f.pozivi[0][1]["Authorization"], "Bearer tajna")
        self.assertIn("q=mlijeko", f.pozivi[0][0])

    def test_cijene_po_poslovnici_s_akcijom(self):
        f = LazniFetch({"/v1/prices/": {"store_prices": [
            {"chain": "konzum", "ean": "111", "regular_price": "2.00", "special_price": "1.50",
             "store": TRGOVINA_KONZUM},
            {"chain": "konzum", "ean": "222", "regular_price": 1.00, "special_price": None,
             "store": TRGOVINA_KONZUM},
        ]}})
        ducani, cijene = CijeneAPI("k", fetch=f).cijene(["111", "222"], 45.81, 15.97, 5)
        self.assertEqual(list(ducani), ["konzum:PJ50"])
        self.assertEqual(ducani["konzum:PJ50"].naziv, "Konzum")
        self.assertEqual(cijene["konzum:PJ50"], {"111": 1.50, "222": 1.00})

    def test_cijene_bez_koordinata_spaja_s_popisom_ducana(self):
        trgovina = {k: v for k, v in TRGOVINA_KONZUM.items() if k not in ("lat", "lon")}
        f = LazniFetch({
            "/v1/prices/": {"store_prices": [
                {"chain": "konzum", "ean": "111", "regular_price": 2.0, "store": trgovina}]},
            "/v1/stores/": {"stores": [TRGOVINA_KONZUM]},
        })
        ducani, cijene = CijeneAPI("k", fetch=f).cijene(["111"], 45.81, 15.97, 5)
        self.assertAlmostEqual(ducani["konzum:PJ50"].lat, 45.8130)
        self.assertEqual(cijene["konzum:PJ50"]["111"], 2.0)

    def test_pogresan_kljuc_daje_jasnu_poruku(self):
        f = LazniFetch({"/v1/products/": GreskaMreze("api.cijene.dev je vratio HTTP 401: nope")})
        with self.assertRaisesRegex(GreskaMreze, "API ključ"):
            CijeneAPI("los", fetch=f).trazi_proizvode("x")

    def test_bez_kljuca(self):
        with self.assertRaises(ValueError):
            CijeneAPI("")


class TestRute(unittest.TestCase):
    def setUp(self):
        self.ducani = [Ducan("a", "konzum", "Konzum", "x", 45.82, 15.98),
                       Ducan("b", "lidl", "Lidl", "y", 45.80, 15.95)]

    def test_matrica_iz_osrm(self):
        f = LazniFetch({"/routed-car/table/": {
            "code": "Ok",
            "distances": [[0, 1200, 2500], [1300, 0, 3000], [2400, 3100, 0]],
            "durations": [[0, 180, 300], [200, 0, 360], [290, 370, 0]],
        }})
        m = rute.matrica("auto", (45.81, 15.97), self.ducani, fetch=f)
        self.assertFalse(m.procjena)
        self.assertAlmostEqual(m.km[0][1], 1.2)
        self.assertAlmostEqual(m.sati[0][2], 300 / 3600)
        self.assertIn("15.970000,45.810000", f.pozivi[0][0])

    def test_bez_interneta_koristi_procjenu(self):
        f = LazniFetch({"/routed-foot/": GreskaMreze("nema mreže")})
        m = rute.matrica("pjesice", (45.81, 15.97), self.ducani, fetch=f)
        self.assertTrue(m.procjena)
        self.assertGreater(m.km[0][1], 0.5)
        self.assertAlmostEqual(m.sati[0][1], m.km[0][1] / 5.0)

    def test_geometrija_rute(self):
        f = LazniFetch({"/routed-bike/route/": {"code": "Ok", "routes": [
            {"geometry": {"coordinates": [[15.97, 45.81], [15.98, 45.82]]}}]}})
        g = rute.geometrija("bicikl", [(45.81, 15.97), (45.82, 15.98)], fetch=f)
        self.assertEqual(g["tocke"], [[45.81, 15.97], [45.82, 15.98]])
        self.assertFalse(g["procjena"])


if __name__ == "__main__":
    unittest.main()
