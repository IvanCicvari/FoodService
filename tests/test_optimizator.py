import unittest

from gdjekupiti.optimizator import (
    Artikl,
    Ducan,
    Matrica,
    ParametriPuta,
    optimiziraj,
)


def matrica_iz_km(kljucevi, km, brzina_kmh=30.0):
    """Pomoćna: matrica gdje je vrijeme izvedeno iz km uz stalnu brzinu."""
    sati = [[d / brzina_kmh for d in red] for red in km]
    return Matrica(kljucevi=kljucevi, km=km, sati=sati)


class TestOptimizator(unittest.TestCase):
    def setUp(self):
        self.ducani = {
            "konzum-1": Ducan("konzum-1", "konzum", "Konzum", "Ilica 1", 45.81, 15.97),
            "lidl-1": Ducan("lidl-1", "lidl", "Lidl", "Savska 2", 45.80, 15.96),
        }
        self.artikli = [
            Artikl("mlijeko", "Mlijeko 1 L", 1, ["111"]),
            Artikl("kruh", "Kruh", 1, ["222"]),
        ]
        # Konzum: mlijeko 2.00, kruh 1.00 ; Lidl: mlijeko 1.20, kruh 1.50
        self.cijene = {
            "konzum-1": {"111": 2.00, "222": 1.00},
            "lidl-1": {"111": 1.20, "222": 1.50},
        }

    def test_auto_bira_jeftiniji_ukupno_s_gorivom(self):
        # start -> konzum 1 km, start -> lidl 1.5 km, konzum <-> lidl 1 km
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 1.0, 1.5], [1.0, 0, 1.0], [1.5, 1.0, 0]],
        )
        p = ParametriPuta(nacin="auto", potrosnja_l_100km=6.0, cijena_goriva=1.50,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=10, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, self.cijene, m, p)
        najbolja = r["najbolja"]
        # Konzum sam: 3.00 + 2 km * 0.09 = 3.18 ; Lidl sam: 2.70 + 3 km * 0.09 = 2.97
        # Lidl+Konzum: 2.20 + (1.5+1+1) km * 0.09 = 2.515
        self.assertEqual({d["kljuc"] for d in najbolja["ducani"]}, {"konzum-1", "lidl-1"})
        self.assertAlmostEqual(najbolja["artikli_iznos"], 2.20, places=2)
        self.assertAlmostEqual(najbolja["km"], 3.5, places=3)
        self.assertAlmostEqual(najbolja["ukupno"], 2.515, places=3)
        self.assertEqual(r["najbolji_jedan"]["ducani"][0]["kljuc"], "lidl-1")
        self.assertAlmostEqual(r["usteda_vs_jedan"], 2.97 - 2.515, places=3)

    def test_skup_put_ostaje_u_jednom_ducanu(self):
        # Lidl je daleko (20 km) pa se podjela ne isplati
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 1.0, 20.0], [1.0, 0, 20.0], [20.0, 20.0, 0]],
        )
        p = ParametriPuta(nacin="auto", potrosnja_l_100km=6.0, cijena_goriva=1.50,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=30, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, self.cijene, m, p)
        self.assertEqual([d["kljuc"] for d in r["najbolja"]["ducani"]], ["konzum-1"])
        self.assertAlmostEqual(r["usteda_vs_jedan"], 0.0, places=6)

    def test_pjesice_vrijeme_ima_cijenu(self):
        # Pješice 5 km/h, sat vrijedi 10 €: svaki km košta 2 € vremena
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 0.5, 1.5], [0.5, 0, 1.2], [1.5, 1.2, 0]],
            brzina_kmh=5.0,
        )
        p = ParametriPuta(nacin="pjesice", potrosnja_l_100km=6.0, cijena_goriva=1.50,
                          vrijednost_sata=10.0, racunaj_vrijeme=False, max_km=5, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, self.cijene, m, p)
        # Konzum: 3.00 + 1 km*2 = 5.00 ; Lidl: 2.70 + 3 km*2 = 8.70 -> Konzum
        self.assertEqual([d["kljuc"] for d in r["najbolja"]["ducani"]], ["konzum-1"])
        self.assertAlmostEqual(r["najbolja"]["trosak_goriva"], 0.0)
        self.assertAlmostEqual(r["najbolja"]["trosak_vremena"], 2.0, places=3)

    def test_max_udaljenost_izbacuje_ducan(self):
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 1.0, 3.0], [1.0, 0, 2.5], [3.0, 2.5, 0]],
        )
        p = ParametriPuta(nacin="pjesice", potrosnja_l_100km=0, cijena_goriva=0,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=2, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, self.cijene, m, p)
        kljucevi = {d["kljuc"] for o in r["opcije"] for d in o["ducani"]}
        self.assertEqual(kljucevi, {"konzum-1"})
        self.assertEqual(r["broj_ducana_u_dometu"], 1)

    def test_bilo_koji_takav_uzima_najjeftiniji_ean(self):
        artikli = [Artikl("mlijeko", "Mlijeko 1 L", 2, ["111", "333"])]
        cijene = {"konzum-1": {"111": 2.00, "333": 1.10}, "lidl-1": {"111": 1.20}}
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 1.0, 1.0], [1.0, 0, 1.0], [1.0, 1.0, 0]],
        )
        p = ParametriPuta(nacin="pjesice", potrosnja_l_100km=0, cijena_goriva=0,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=5, max_ducana=1)
        r = optimiziraj(artikli, self.ducani, cijene, m, p)
        d = r["najbolja"]["ducani"][0]
        self.assertEqual(d["kljuc"], "konzum-1")
        self.assertEqual(d["artikli"][0]["ean"], "333")
        self.assertAlmostEqual(d["artikli"][0]["cijena"], 2.20, places=2)

    def test_nedostupan_artikl_se_oznaci(self):
        artikli = self.artikli + [Artikl("kava", "Kava", 1, ["999"])]
        cijene = dict(self.cijene)
        cijene["konzum-1"] = {**cijene["konzum-1"], "999": 4.0}
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 1.0, 1.0], [1.0, 0, 1.0], [1.0, 1.0, 0]],
        )
        p = ParametriPuta(nacin="pjesice", potrosnja_l_100km=0, cijena_goriva=0,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=5, max_ducana=1)
        r = optimiziraj(artikli, self.ducani, cijene, m, p)
        # Samo Konzum ima kavu pa je jedina potpuna opcija
        self.assertEqual(r["najbolja"]["ducani"][0]["kljuc"], "konzum-1")
        self.assertEqual(r["najbolja"]["nedostaje"], [])
        lidl = [o for o in r["opcije"] if o["ducani"][0]["kljuc"] == "lidl-1"][0]
        self.assertEqual(lidl["nedostaje"], ["Kava"])

    def test_nema_ducana_u_dometu(self):
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1"],
            [[0, 9.0, 9.0], [9.0, 0, 1.0], [9.0, 1.0, 0]],
        )
        p = ParametriPuta(nacin="pjesice", potrosnja_l_100km=0, cijena_goriva=0,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=2, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, self.cijene, m, p)
        self.assertIsNone(r["najbolja"])
        self.assertEqual(r["opcije"], [])

    def test_ducan_bez_artikala_ne_ulazi_u_kombinaciju(self):
        self.ducani["spar-1"] = Ducan("spar-1", "spar", "Spar", "Vukovarska 3", 45.8, 15.98)
        cijene = dict(self.cijene)
        cijene["spar-1"] = {"111": 5.0, "222": 5.0}
        m = matrica_iz_km(
            ["start", "konzum-1", "lidl-1", "spar-1"],
            [[0, 1, 1, 1], [1, 0, 1, 1], [1, 1, 0, 1], [1, 1, 1, 0]],
        )
        p = ParametriPuta(nacin="auto", potrosnja_l_100km=6.0, cijena_goriva=1.5,
                          vrijednost_sata=0.0, racunaj_vrijeme=False, max_km=5, max_ducana=3)
        r = optimiziraj(self.artikli, self.ducani, cijene, m, p)
        for o in r["opcije"]:
            for d in o["ducani"]:
                self.assertTrue(d["artikli"], f"Dućan {d['kljuc']} nema artikala u opciji")


if __name__ == "__main__":
    unittest.main()
