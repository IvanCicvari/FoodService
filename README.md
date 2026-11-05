# Gdje kupiti?

Osobna web aplikacija koja za tvoj popis za kupovinu izračuna gdje je **ukupno** najjeftinije:
cijena artikala plus trošak puta. Pokazuje i rutu na karti.

Primjer: Konzum je 1 km daleko, a mlijeko tamo košta 2 €. Lidl je 1,5 km daleko, a mlijeko košta 1,20 €.
Aplikacija uračuna gorivo (ili vrijeme ako ideš pješice) i kaže isplati li se ići u Lidl.
Kaže i isplati li se podijeliti kupovinu na 2–3 dućana.

## Pokretanje na Windowsu

1. Instaliraj **Python 3.10 ili noviji** s <https://www.python.org/downloads/>.
   Pri instalaciji označi **Add python.exe to PATH**.
2. Raspakiraj mapu `gdje-kupiti` bilo gdje, npr. u `Dokumenti`.
3. Dvoklik na **`pokreni-demo.bat`** za isprobavanje s izmišljenim podacima.
   Za to ne treba ni ključ ni internet.
4. Za stvarne cijene zatraži besplatni API ključ na <https://cijene.dev>.
   Besplatan je za nekomercijalnu upotrebu.
5. Dvoklik na **`pokreni.bat`**. Otvorit će se preglednik na `http://127.0.0.1:8765`.
6. U **Postavkama** upiši API ključ, kućnu adresu, gorivo i potrošnju auta.

Dok koristiš aplikaciju, crni prozor mora ostati otvoren. Zatvaranjem prozora gasiš aplikaciju.

| Datoteka | Čemu služi |
|---|---|
| `pokreni.bat` | normalno pokretanje |
| `pokreni-demo.bat` | izmišljeni dućani i cijene, za isprobavanje |
| `pokreni-za-mobitel.bat` | aplikacija je dostupna i s mobitela na kućnoj Wi-Fi mreži; adresu ispiše u prozoru |
| `provjeri-veze.bat` | provjeri rade li svi vanjski servisi; korisno ako nešto ne radi |

## Kako se koristi

1. **Potraži proizvod** (npr. „mlijeko 1 l”).
   - **Točno ovaj**: uspoređuje se točno taj proizvod (isti barkod) u svim dućanima.
   - **Bilo koji takav**: označi više sličnih proizvoda i dodaj ih kao grupu.
     U svakom dućanu uzima se najjeftiniji od njih.
     Grupa se zapamti, pa je idući put dodaješ jednim klikom.
2. Odaberi **Auto**, **Pješice** ili **Bicikl**.
3. Polazište je kućna adresa. Promijeniti ga možeš upisom druge adrese ili gumbom „Moja lokacija”.
4. Klikni **Izračunaj**. Dobiješ:
   - najisplativiju opciju, s raspodjelom artikala po dućanima
   - koliko štediš u odnosu na najbolji pojedinačni dućan
   - usporedbu ostalih opcija; klik na opciju pokaže je na karti

## Kako računa

```
ukupno = cijena artikala + trošak puta

auto:            trošak puta = km × potrošnja/100 × cijena goriva   (+ vrijeme, ako je uključeno)
pješice/bicikl:  trošak puta = sati puta × koliko ti vrijedi sat
```

- Put je kružni: polazište → dućan(i) → polazište, redoslijedom koji je najkraći.
- Dućani dalje od zadane najveće udaljenosti se ne gledaju. Udaljenost se zadaje posebno za auto, bicikl i pješačenje.
- Isprobaju se sve kombinacije od 1 do 3 dućana (u Postavkama možeš ograničiti na 1 ili 2).
- Dućan se ne posjećuje ako se u njemu ne bi ništa kupilo.
- Ako se artikl ne nalazi ni u jednom dućanu u dometu, aplikacija to jasno napiše.
- Akcijska cijena se uzima kad je niža od redovne.

## Odakle su podaci

| Podatak | Izvor |
|---|---|
| Cijene u dućanima | [cijene.dev](https://cijene.dev): pročišćeni cjenici koje trgovci moraju objavljivati |
| Cijena goriva | [HAK](https://www.hak.hr/info/cijene-goriva/), podaci Ministarstva gospodarstva (mzoe-gor.hr); uzima se cijena koju ima većina postaja, osvježava se jednom dnevno |
| Rute i udaljenosti | OSRM poslužitelji FOSSGIS-a nad OpenStreetMapom (`routing.openstreetmap.de`) |
| Adrese | Nominatim (OpenStreetMap) |
| Karta | OpenStreetMap kroz Leaflet |

Ako servis za rute ne radi, aplikacija i dalje računa. Koristi zračnu liniju × 1,3, a to je jasno označeno.
Ako cijena goriva nije dostupna, koristi se zadnja poznata cijena.
U Postavkama možeš upisati i vlastitu cijenu goriva.

Svi su ovi servisi besplatni za osobnu upotrebu. Ako aplikaciju jednom objaviš javno, treba provjeriti uvjete:
cijene.dev ima pretplatu za komercijalnu upotrebu, a javni OSM poslužitelji nisu za veliki promet.

## Ako nešto ne radi

Pokreni `provjeri-veze.bat`. Za svaki servis ispiše radi li i pokaže početak odgovora s cijene.dev.

- **„cijene.dev ne prihvaća API ključ”**: ponovo zalijepi ključ u Postavkama.
- **Pretraga radi, a izračun ne nađe dućane**: povećaj najveću udaljenost u Postavkama.
- **Port 8765 je zauzet**: aplikacija je već pokrenuta u drugom prozoru.
- **Na mobitelu „Moja lokacija” ne radi**: preglednik daje GPS samo preko HTTPS-a ili na samom računalu.
  Na mobitelu upiši adresu.

## Gdje je što (za uređivanje)

```
app.py                     web server i API rute; pokretanje i opcije (--demo, --lan, --provjeri)
gdjekupiti/optimizator.py  izračun najisplativije kupovine (bez interneta, lako se testira)
gdjekupiti/cijene_api.py   klijent za cijene.dev; ako API promijeni polja, popravak ide ovdje
gdjekupiti/gorivo.py       čitanje cijena goriva s HAK-ove stranice
gdjekupiti/rute.py         udaljenosti i rute (OSRM) + procjena bez interneta
gdjekupiti/geo.py          traženje adresa (Nominatim)
gdjekupiti/demo.py         izmišljeni podaci za demo način
gdjekupiti/pohrana.py      spremanje u mapu data/
gdjekupiti/servis.py       povezuje sve gore navedeno
static/                    sučelje (index.html, app.js, style.css)
tests/                     testovi
data/                      tvoje postavke, popis i grupe (ne ide na GitHub)
```

Aplikacija koristi samo standardnu Python biblioteku, pa nema ništa za instalirati.

Testovi se pokreću ovako:

```
python -m unittest discover -s tests -t .
```

## Licenca podataka

Podaci o cijenama dolaze s cijene.dev i javni su temeljem Vladine odluke o objavi cjenika.
Uvjete korištenja API-ja propisuje cijene.dev.
Karte i rute: © OpenStreetMap suradnici.
