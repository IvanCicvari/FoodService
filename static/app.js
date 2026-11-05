"use strict";

// ---------- Konstante ----------
const LANCI = {
  konzum: "Konzum", lidl: "Lidl", kaufland: "Kaufland", spar: "Spar", plodine: "Plodine",
  studenac: "Studenac", tommy: "Tommy", eurospin: "Eurospin", dm: "dm", ktc: "KTC",
  metro: "Metro", zabac: "Žabac", ribola: "Ribola", ntl: "NTL", boso: "Boso",
  trgocentar: "Trgocentar", vrutak: "Vrutak", brodokomerc: "Brodokomerc", lorenco: "Lorenco",
  roto: "Roto", bure: "Bure", dukat: "Dukat",
};
const BOJE = {
  konzum: "#c8102e", lidl: "#0050aa", kaufland: "#b5121b", spar: "#00843d", plodine: "#e87511",
  studenac: "#6b3fa0", tommy: "#d1006f", eurospin: "#003b7e", dm: "#2b2d7a", ktc: "#00965e",
  metro: "#002d72",
};
const ZAGREB = [45.8131, 15.9772];
const eur = new Intl.NumberFormat("hr-HR", { style: "currency", currency: "EUR" });
const broj = new Intl.NumberFormat("hr-HR", { maximumFractionDigits: 1 });

const stanje = {
  demo: false,
  postavke: null,
  popis: [],
  grupe: {},
  nacin: "auto",
  polaziste: null, // null = kućna adresa
  rezultat: null,
  odabrana: 0,
  pretraga: [],
  upit: "",
  oznaceni: new Map(), // ean -> proizvod
  gorivo: null,
};

// ---------- Pomoćne ----------
const $ = (id) => document.getElementById(id);

function el(tag, svojstva = {}, ...djeca) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(svojstva)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "style") e.style.cssText = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const d of djeca.flat()) {
    if (d === null || d === undefined || d === false) continue;
    e.append(d instanceof Node ? d : document.createTextNode(String(d)));
  }
  return e;
}

async function api(metoda, putanja, tijelo) {
  const opcije = { method: metoda, headers: {} };
  if (metoda !== "GET") {
    opcije.headers["X-Gdje-Kupiti"] = "1";
    opcije.headers["Content-Type"] = "application/json";
    opcije.body = JSON.stringify(tijelo ?? {});
  }
  let odg;
  try {
    odg = await fetch(putanja, opcije);
  } catch {
    throw new Error("Aplikacija ne odgovara. Je li prozor s aplikacijom (pokreni.bat) još otvoren?");
  }
  let podaci = null;
  try { podaci = await odg.json(); } catch { /* prazan odgovor */ }
  if (!odg.ok) throw new Error(podaci?.greska || `Greška ${odg.status}`);
  return podaci;
}

function obavijest(tekst, { vrsta = "", gumb = null, trajno = false } = {}) {
  const o = el("div", { class: `obavijest ${vrsta}` }, el("span", {}, tekst));
  if (gumb) o.append(el("button", { class: "gumb malo", type: "button", onclick: gumb.akcija }, gumb.tekst));
  o.append(el("button", { class: "gumb-tekst malo", type: "button", "aria-label": "Zatvori", onclick: () => o.remove() }, "✕"));
  $("obavijesti").append(o);
  if (!trajno) setTimeout(() => o.remove(), 7000);
  return o;
}

function greska(e) {
  obavijest(e.message || String(e), { vrsta: "greska" });
}

function nazivProizvoda(p) {
  const velicina = [p.kolicina, p.jedinica].filter(Boolean).join(" ");
  const dijelovi = [p.naziv];
  if (velicina && !p.naziv.toLowerCase().includes(velicina.toLowerCase())) dijelovi.push(velicina);
  return dijelovi.join(" ") + (p.marka ? ` (${p.marka})` : "");
}

function nazivLanca(kod) {
  return LANCI[kod] || (kod ? kod[0].toUpperCase() + kod.slice(1) : "?");
}

function boja(kod) {
  return BOJE[kod] || "#4d6158";
}

function cijenaGoriva() {
  const g = stanje.postavke.gorivo;
  if (g.rucna_cijena) return { cijena: Number(g.rucna_cijena), izvor: "ručno upisana" };
  const c = stanje.gorivo?.cijene?.[g.vrsta];
  if (c) return { cijena: c, izvor: `${stanje.gorivo.izvor || ""} ${stanje.gorivo.datum || ""}`.trim() };
  return null;
}

// ---------- Spremanje ----------
async function spremiPopis() {
  stanje.popis = await api("PUT", "/api/popis", stanje.popis);
  prikaziPopis();
}

async function spremiGrupe() {
  stanje.grupe = await api("PUT", "/api/grupe", stanje.grupe);
  prikaziZapamceno();
}

// ---------- Pretraga ----------
async function trazi(e) {
  e.preventDefault();
  const upit = $("upit").value.trim();
  if (upit.length < 2) return;
  stanje.upit = upit;
  $("rezultati-pretrage").hidden = false;
  $("pretraga-info").innerHTML = "";
  $("pretraga-info").append(el("span", { class: "ucitavanje" }), "Tražim…");
  $("pretraga-lista").replaceChildren();
  try {
    stanje.pretraga = await api("GET", `/api/proizvodi?q=${encodeURIComponent(upit)}`);
    prikaziPretragu();
  } catch (err) {
    $("pretraga-info").textContent = "Pretraga nije uspjela.";
    greska(err);
  }
}

function prikaziPretragu() {
  const lista = $("pretraga-lista");
  lista.replaceChildren();
  $("pretraga-info").textContent = stanje.pretraga.length
    ? `${stanje.pretraga.length} rezultata za „${stanje.upit}”. Označi slične za „bilo koji takav”.`
    : `Nema rezultata za „${stanje.upit}”. Probaj kraći upit.`;
  for (const p of stanje.pretraga) {
    const kvacica = el("input", {
      type: "checkbox", "aria-label": `Označi ${p.naziv}`,
      onchange: (e) => {
        if (e.target.checked) stanje.oznaceni.set(p.ean, p); else stanje.oznaceni.delete(p.ean);
        prikaziGrupaTraku();
      },
    });
    kvacica.checked = stanje.oznaceni.has(p.ean);
    const detalji = [];
    if (p.cijena_od != null) {
      detalji.push(el("span", { class: "cijena-od" }, `od ${eur.format(p.cijena_od)}`));
      if (p.najjeftinije_u) detalji.push(` · ${p.najjeftinije_u}`);
      if (p.broj_lanaca) detalji.push(` · ${p.broj_lanaca} ${p.broj_lanaca === 1 ? "lanac" : "lanaca"}`);
    }
    lista.append(el("li", {},
      kvacica,
      el("div", {},
        el("div", { class: "proizvod-naziv" }, nazivProizvoda(p)),
        el("div", { class: "proizvod-detalji" }, ...detalji),
      ),
      el("button", { class: "gumb malo", type: "button", onclick: () => dodajTocno(p) }, "Točno ovaj"),
    ));
  }
  prikaziGrupaTraku();
}

function prikaziGrupaTraku() {
  const n = stanje.oznaceni.size;
  $("grupa-traka").hidden = n === 0;
  $("grupa-broj").textContent = `Označeno: ${n}`;
}

function zatvoriPretragu() {
  $("rezultati-pretrage").hidden = true;
  stanje.oznaceni.clear();
  stanje.pretraga = [];
}

async function dodajTocno(p) {
  const id = `e${p.ean}`;
  const postoji = stanje.popis.find((s) => s.id === id);
  if (postoji) postoji.kolicina = Math.min(99, postoji.kolicina + 1);
  else stanje.popis.push({
    id, naziv: nazivProizvoda(p), kolicina: 1, tip: "tocno", eanovi: [p.ean],
    proizvodi: [{ ean: p.ean, naziv: nazivProizvoda(p) }],
  });
  try {
    await spremiPopis();
    obavijest(`Dodano: ${nazivProizvoda(p)}`);
  } catch (err) { greska(err); }
}

function otvoriGrupaDijalog() {
  const naziv = stanje.upit ? stanje.upit[0].toUpperCase() + stanje.upit.slice(1) : "";
  $("grupa-naziv").value = naziv;
  $("grupa-dijalog").showModal();
  $("grupa-naziv").select();
}

async function dodajGrupu(e) {
  e.preventDefault();
  const naziv = $("grupa-naziv").value.trim();
  if (!naziv) return;
  const proizvodi = [...stanje.oznaceni.values()].map((p) => ({ ean: p.ean, naziv: nazivProizvoda(p) }));
  let eanovi = proizvodi.map((p) => p.ean);
  const postoji = stanje.popis.find((s) => s.tip === "grupa" && s.naziv === naziv);
  if (postoji) {
    // Ista grupa već postoji: dodaj nove proizvode u nju umjesto duplikata
    for (const p of proizvodi) {
      if (!postoji.eanovi.includes(p.ean)) { postoji.eanovi.push(p.ean); postoji.proizvodi.push(p); }
    }
    eanovi = postoji.eanovi;
    stanje.grupe[naziv] = { eanovi: postoji.eanovi, proizvodi: postoji.proizvodi };
  } else {
    stanje.popis.push({ id: `g${Date.now()}`, naziv, kolicina: 1, tip: "grupa", eanovi, proizvodi });
    stanje.grupe[naziv] = { eanovi, proizvodi };
  }
  $("grupa-dijalog").close();
  try {
    await spremiPopis();
    await spremiGrupe();
    stanje.oznaceni.clear();
    prikaziPretragu();
    obavijest(`Dodano „${naziv}” (bilo koji od ${eanovi.length} proizvoda). Zapamćeno za idući put.`);
  } catch (err) { greska(err); }
}

// ---------- Zapamćene grupe ----------
function prikaziZapamceno() {
  const imena = Object.keys(stanje.grupe).sort((a, b) => a.localeCompare(b, "hr"));
  $("zapamceno").hidden = imena.length === 0;
  const lista = $("zapamceno-lista");
  lista.replaceChildren();
  for (const ime of imena) {
    lista.append(el("span", { class: "cip-par" },
      el("button", { class: "cip", type: "button", title: "Dodaj na popis", onclick: () => dodajZapamceno(ime) }, `+ ${ime}`),
      el("button", {
        class: "ukloni", type: "button", title: `Zaboravi „${ime}”`, "aria-label": `Zaboravi ${ime}`,
        onclick: async () => {
          delete stanje.grupe[ime];
          try { await spremiGrupe(); } catch (err) { greska(err); }
        },
      }, "✕"),
    ));
  }
}

async function dodajZapamceno(ime) {
  const g = stanje.grupe[ime];
  const postoji = stanje.popis.find((s) => s.tip === "grupa" && s.naziv === ime);
  if (postoji) postoji.kolicina = Math.min(99, postoji.kolicina + 1);
  else stanje.popis.push({ id: `g${Date.now()}`, naziv: ime, kolicina: 1, tip: "grupa", eanovi: g.eanovi, proizvodi: g.proizvodi });
  try { await spremiPopis(); } catch (err) { greska(err); }
}

// ---------- Popis ----------
function prikaziPopis() {
  const ul = $("popis");
  ul.replaceChildren();
  $("popis-prazan").hidden = stanje.popis.length > 0;
  const komada = stanje.popis.reduce((s, x) => s + x.kolicina, 0);
  $("broj-artikala").textContent = stanje.popis.length ? `${stanje.popis.length} artikala · ${komada} kom` : "";

  for (const stavka of stanje.popis) {
    const info = el("div", {}, el("div", { class: "proizvod-naziv" }, stavka.naziv));
    if (stavka.tip === "grupa") {
      const clanovi = el("ul", { class: "clanovi", hidden: true },
        ...(stavka.proizvodi || []).map((p) => el("li", {}, p.naziv)));
      info.append(
        el("button", {
          class: "znacka grupa", type: "button", "aria-expanded": "false",
          onclick: (e) => {
            clanovi.hidden = !clanovi.hidden;
            e.target.setAttribute("aria-expanded", String(!clanovi.hidden));
          },
        }, `bilo koji od ${stavka.eanovi.length}`),
        clanovi,
      );
    } else {
      info.append(el("span", { class: "znacka" }, "točno ovaj"));
    }
    ul.append(el("li", {},
      info,
      el("div", { class: "kolicina" },
        el("button", { type: "button", "aria-label": "Manje", onclick: () => promijeniKolicinu(stavka, -1) }, "−"),
        el("span", {}, stavka.kolicina),
        el("button", { type: "button", "aria-label": "Više", onclick: () => promijeniKolicinu(stavka, 1) }, "+"),
      ),
      el("button", { class: "ukloni", type: "button", "aria-label": `Ukloni ${stavka.naziv}`, onclick: () => ukloni(stavka) }, "✕"),
    ));
  }
}

async function promijeniKolicinu(stavka, za) {
  stavka.kolicina = Math.max(1, Math.min(99, stavka.kolicina + za));
  try { await spremiPopis(); } catch (err) { greska(err); }
}

async function ukloni(stavka) {
  stanje.popis = stanje.popis.filter((s) => s !== stavka);
  try { await spremiPopis(); } catch (err) { greska(err); }
}

// ---------- Način puta i polazište ----------
function prikaziNacin() {
  for (const b of document.querySelectorAll(".nacin")) {
    b.setAttribute("aria-checked", String(b.dataset.nacin === stanje.nacin));
  }
  const p = stanje.postavke;
  const km = p.max_km[stanje.nacin];
  let opis;
  if (stanje.nacin === "auto") {
    const g = cijenaGoriva();
    const gorivo = g ? `${eur.format(g.cijena)}/l` : "cijena goriva se učitava";
    opis = `Gorivo: ${broj.format(p.gorivo.potrosnja)} l/100 km, ${gorivo}`;
    if (p.racunaj_vrijeme_auto) opis += `, vrijeme ${eur.format(p.vrijednost_sata)}/h`;
    opis += `. Dućani do ${broj.format(km)} km.`;
  } else {
    opis = `Vrijeme vrijedi ${eur.format(p.vrijednost_sata)}/h. Dućani do ${broj.format(km)} km.`;
  }
  $("nacin-opis").textContent = opis;
}

async function odaberiNacin(nacin) {
  stanje.nacin = nacin;
  prikaziNacin();
  try {
    stanje.postavke = await api("PUT", "/api/postavke", { zadnji_nacin: nacin });
  } catch { /* nije bitno ako ne uspije */ }
}

function prikaziPolaziste() {
  const t = $("polaziste-tekst");
  const dom = stanje.postavke.dom;
  if (stanje.polaziste) {
    t.textContent = stanje.polaziste.adresa;
    $("promijeni-polaziste").textContent = "Vrati na kuću";
  } else {
    t.textContent = dom.lat != null ? `Kuća · ${dom.adresa}` : "Kućna adresa nije upisana";
    $("promijeni-polaziste").textContent = "Promijeni";
  }
  t.title = t.textContent;
}

function prikaziAdrese(lista, ul, odabir) {
  ul.replaceChildren();
  if (!lista.length) {
    ul.append(el("li", { class: "tiho", style: "padding:8px 10px" }, "Nisam našao adresu. Dodaj grad, npr. „Ilica 100, Zagreb”."));
    return;
  }
  for (const a of lista) {
    ul.append(el("li", {}, el("button", { type: "button", onclick: () => odabir(a) }, a.adresa)));
  }
}

async function traziPolaziste(e) {
  e.preventDefault();
  const upit = $("polaziste-upit").value.trim();
  if (upit.length < 3) return;
  try {
    const lista = await api("GET", `/api/adresa?q=${encodeURIComponent(upit)}`);
    prikaziAdrese(lista, $("polaziste-rezultati"), (a) => {
      stanje.polaziste = { ...a, adresa: kratkaAdresa(a.adresa) };
      $("polaziste-forma").hidden = true;
      $("polaziste-rezultati").replaceChildren();
      prikaziPolaziste();
      postaviPocetnuKartu();
    });
  } catch (err) { greska(err); }
}

function kratkaAdresa(puna) {
  return puna.split(",").slice(0, 3).join(",").trim();
}

function mojaLokacija() {
  if (!navigator.geolocation) return greska(new Error("Preglednik ne podržava lokaciju."));
  navigator.geolocation.getCurrentPosition(
    (poz) => {
      stanje.polaziste = { lat: poz.coords.latitude, lon: poz.coords.longitude, adresa: "Moja trenutna lokacija" };
      $("polaziste-forma").hidden = true;
      prikaziPolaziste();
      postaviPocetnuKartu();
    },
    () => greska(new Error("Lokacija nije dostupna. Na mobitelu preko kućne mreže preglednik je ne daje; upiši adresu.")),
    { enableHighAccuracy: true, timeout: 10000 },
  );
}

// ---------- Izračun ----------
async function izracunaj() {
  const gumb = $("izracunaj");
  if (!stanje.popis.length) return greska(new Error("Popis je prazan. Dodaj barem jedan artikl."));
  gumb.disabled = true;
  gumb.replaceChildren(el("span", { class: "ucitavanje" }), "Računam…");
  try {
    stanje.rezultat = await api("POST", "/api/izracun", { nacin: stanje.nacin, polaziste: stanje.polaziste });
    stanje.odabrana = 0;
    prikaziRezultat();
    await nacrtajOpciju();
    if (window.matchMedia("(max-width: 959px)").matches) $("rezultat").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    greska(err);
  } finally {
    gumb.disabled = false;
    gumb.textContent = "Izračunaj gdje je najisplativije";
  }
}

function imenaDucana(o) {
  return o.ducani.map((d) => d.naziv).join(" + ");
}

function opisPuta(o, r) {
  const dijelovi = [`${broj.format(o.km)} km`, `${o.minuta} min`];
  let put = `put ${eur.format(o.trosak_puta)}`;
  if (r.nacin === "auto" && o.trosak_vremena > 0) {
    put += ` (gorivo ${eur.format(o.trosak_goriva)} + vrijeme ${eur.format(o.trosak_vremena)})`;
  } else if (r.nacin === "auto") {
    put += " (gorivo)";
  } else {
    put += " (vrijeme)";
  }
  return `Artikli ${eur.format(o.artikli_iznos)} + ${put} · ${dijelovi.join(" · ")}`;
}

function prikaziRezultat() {
  const r = stanje.rezultat;
  const s = $("rezultat");
  s.hidden = false;
  s.replaceChildren();

  if (!r.najbolja) {
    s.append(el("h2", {}, "Nema rezultata"));
    s.append(el("p", {}, r.broj_ducana_u_dometu === 0
      ? `Nema dućana do ${broj.format(r.parametri.max_km)} km od polazišta. Povećaj udaljenost u Postavkama ili odaberi drugi način puta.`
      : "Nijedan dućan u blizini nema artikle s popisa."));
    return;
  }

  const o = r.opcije[stanje.odabrana] || r.najbolja;
  const jeNajbolja = o === r.opcije[0];
  s.append(el("h2", {}, jeNajbolja ? "Najisplativije" : `Opcija ${stanje.odabrana + 1}`));
  const pob = el("div", { class: "pobjednik" },
    el("div", { class: "pobjednik-ducani" }, imenaDucana(o)),
    el("div", { class: "pobjednik-iznos" }, eur.format(o.ukupno)),
    el("div", { class: "razrada" }, opisPuta(o, r)),
  );
  const nj = r.najbolji_jedan;
  if (jeNajbolja && nj) {
    if (o.ducani.length > 1 && r.usteda_vs_jedan >= 0.01) {
      pob.append(el("span", { class: "usteda" },
        `Uštediš ${eur.format(r.usteda_vs_jedan)} u odnosu na sve u ${nj.ducani[0].naziv} (${eur.format(nj.ukupno)})`));
    } else if (o.ducani.length === 1 && stanje.postavke.max_ducana > 1) {
      pob.append(el("span", { class: "usteda" }, "Sve kupi na jednom mjestu. Podjela na više dućana se ne isplati."));
    }
  } else if (!jeNajbolja) {
    const razlika = o.ukupno - r.najbolja.ukupno;
    pob.append(el("span", { class: "razrada" }, `${eur.format(razlika)} skuplje od najisplativije opcije`));
  }
  s.append(pob);

  if (o.nedostaje.length) {
    s.append(el("div", { class: "upozorenje" }, `Ovdje nema: ${o.nedostaje.join(", ")}`));
  }
  if (r.nedostupno_svugdje.length && jeNajbolja) {
    s.append(el("div", { class: "upozorenje" },
      `Nijedan dućan u dometu nema: ${r.nedostupno_svugdje.join(", ")}. Za „bilo koji takav” dodaj još sličnih proizvoda.`));
  }

  o.ducani.forEach((d, i) => {
    s.append(el("div", { class: "ducan-blok" },
      el("div", { class: "ducan-glava" },
        el("span", { class: "redni", style: `background:${boja(d.lanac)}` }, i + 1),
        el("div", {},
          el("div", { class: "ducan-naziv" }, d.naziv),
          el("div", { class: "ducan-adresa" }, `${d.adresa} · ${broj.format(d.km_od_starta)} km od polazišta`),
        ),
        el("span", { class: "iznos" }, eur.format(d.iznos)),
      ),
      el("ul", { class: "stavke" },
        ...d.artikli.map((a) => el("li", {},
          el("span", {}, `${a.kolicina > 1 ? `${a.kolicina} × ` : ""}${a.naziv}`),
          el("span", {}, eur.format(a.cijena)),
        )),
      ),
    ));
  });

  if (r.opcije.length > 1) {
    const box = el("div", { class: "opcije" }, el("h3", {}, "Usporedi opcije"));
    r.opcije.forEach((op, i) => {
      const razlika = op.ukupno - r.najbolja.ukupno;
      box.append(el("button", {
        class: "opcija", type: "button", "aria-pressed": String(i === stanje.odabrana),
        onclick: async () => { stanje.odabrana = i; prikaziRezultat(); await nacrtajOpciju(); },
      },
        el("span", { class: "opcija-ducani" }, imenaDucana(op)),
        el("span", { class: "opcija-iznos" }, eur.format(op.ukupno)),
        el("span", { class: "opcija-detalji" },
          `${op.ducani.map((d) => d.adresa.split(",")[0]).join(" → ")} · ${broj.format(op.km)} km · ${op.minuta} min` +
          (op.nedostaje.length ? ` · nema ${op.nedostaje.length} art.` : "")),
        el("span", { class: "opcija-razlika" }, i === 0 ? "najbolje" : `+${eur.format(razlika)}`),
      ));
    });
    s.append(box);
  }

  const napomene = el("div", { class: "napomene tiho" });
  if (r.parametri.cijena_goriva) {
    napomene.append(el("div", {}, `Gorivo ${eur.format(r.parametri.cijena_goriva)}/l (${r.parametri.izvor_goriva}), potrošnja ${broj.format(r.parametri.potrosnja)} l/100 km.`));
  }
  if (r.parametri.racuna_vrijeme) {
    napomene.append(el("div", {}, `Vrijeme računato po ${eur.format(r.parametri.vrijednost_sata)}/h.`));
  }
  if (r.procjena_udaljenosti) {
    napomene.append(el("div", {}, "Udaljenosti su procjena (zračna linija × 1,3) jer servis za rute nije bio dostupan."));
  }
  napomene.append(el("div", {}, `Usporedio sam ${r.broj_ducana_u_dometu} dućana do ${broj.format(r.parametri.max_km)} km. Cijene su iz cjenika trgovaca i mogu kasniti dan.`));
  if (r.demo) napomene.append(el("div", {}, "DEMO: dućani i cijene su izmišljeni."));
  s.append(napomene);
}

// ---------- Karta ----------
let karta = null;
let slojevi = null;

function inicijalizirajKartu() {
  if (!window.L) {
    $("karta").append(el("div", { class: "karta-prazno" },
      "Karta se nije učitala (nema veze s internetom?). Izračun i dalje radi."));
    return;
  }
  karta = L.map("karta", { zoomControl: true, attributionControl: true });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(karta);
  slojevi = L.layerGroup().addTo(karta);
  postaviPocetnuKartu();
}

function pocetak() {
  if (stanje.polaziste) return [stanje.polaziste.lat, stanje.polaziste.lon];
  const d = stanje.postavke.dom;
  return d.lat != null ? [d.lat, d.lon] : null;
}

function ikonaStart() {
  return L.divIcon({
    className: "", iconSize: [28, 28], iconAnchor: [14, 14],
    html: '<div class="marker start" title="Polazište"><svg viewBox="0 0 24 24" style="width:15px;height:15px"><path d="M4 11l8-7 8 7v9h-5v-6H9v6H4z" fill="currentColor"/></svg></div>',
  });
}

function postaviPocetnuKartu() {
  if (!karta) return;
  slojevi.clearLayers();
  const p = pocetak();
  if (p) {
    L.marker(p, { icon: ikonaStart() }).addTo(slojevi);
    karta.setView(p, 14);
  } else {
    karta.setView(ZAGREB, 12);
  }
}

async function nacrtajOpciju() {
  const r = stanje.rezultat;
  const o = r?.opcije?.[stanje.odabrana];
  $("karta-napomena").hidden = true;
  if (!karta || !o) return;
  slojevi.clearLayers();
  const start = [r.polaziste.lat, r.polaziste.lon];
  L.marker(start, { icon: ikonaStart() }).bindPopup("Polazište").addTo(slojevi);
  const tocke = [start];
  o.ducani.forEach((d, i) => {
    const t = [d.lat, d.lon];
    tocke.push(t);
    L.marker(t, {
      icon: L.divIcon({
        className: "", iconSize: [28, 28], iconAnchor: [14, 14],
        html: `<div class="marker" style="background:${boja(d.lanac)}">${i + 1}</div>`,
      }),
    }).bindPopup(`<b>${escapeHtml(d.naziv)}</b><br>${escapeHtml(d.adresa)}<br>${eur.format(d.iznos)}`).addTo(slojevi);
  });
  tocke.push(start);
  karta.fitBounds(L.latLngBounds(tocke).pad(0.2));

  try {
    const ruta = await api("POST", "/api/ruta", { nacin: r.nacin, tocke });
    if (stanje.rezultat !== r || r.opcije[stanje.odabrana] !== o) return; // u međuvremenu promijenjeno
    L.polyline(ruta.tocke, {
      color: "#1f6f4a", weight: 5, opacity: 0.85, dashArray: ruta.procjena ? "6 8" : null,
    }).addTo(slojevi);
    if (ruta.procjena) {
      $("karta-napomena").hidden = false;
      $("karta-napomena").textContent = "Isprekidana linija je zračna linija, ne stvarna ruta.";
    }
  } catch (err) { greska(err); }
}

function escapeHtml(t) {
  return String(t).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- Postavke ----------
let odabraniDom = null;

async function ucitajGorivo(osvjezi = false) {
  try {
    stanje.gorivo = await api("GET", `/api/gorivo${osvjezi ? "?osvjezi=1" : ""}`);
    if (stanje.gorivo.greska) obavijest(`Cijena goriva: ${stanje.gorivo.greska}`);
  } catch (err) {
    stanje.gorivo = null;
  }
  prikaziNacin();
  prikaziGorivoUPostavkama();
}

function prikaziGorivoUPostavkama() {
  const vrsta = $("p-gorivo").value || stanje.postavke.gorivo.vrsta;
  const c = stanje.gorivo?.cijene?.[vrsta];
  $("p-cijena-auto").textContent = c
    ? `Automatski: ${eur.format(c)}/l (${stanje.gorivo.izvor}${stanje.gorivo.datum ? ", " + stanje.gorivo.datum : ""})`
    : "Automatska cijena trenutno nije dostupna.";
}

function otvoriPostavke() {
  const p = stanje.postavke;
  $("p-kljuc").value = "";
  $("p-kljuc").placeholder = p.api_kljuc_postavljen ? "ključ je spremljen (upiši novi za promjenu)" : "zalijepi ključ";
  $("p-adresa").value = "";
  $("p-adrese").replaceChildren();
  odabraniDom = null;
  $("p-adresa-odabrana").textContent = p.dom.lat != null ? `Spremljeno: ${p.dom.adresa}` : "Adresa još nije upisana.";
  $("p-gorivo").value = p.gorivo.vrsta;
  $("p-potrosnja").value = p.gorivo.potrosnja;
  $("p-rucna-cijena").value = p.gorivo.rucna_cijena ?? "";
  $("p-vrijeme-auto").checked = !!p.racunaj_vrijeme_auto;
  $("p-sat").value = p.vrijednost_sata;
  $("p-km-auto").value = p.max_km.auto;
  $("p-km-bicikl").value = p.max_km.bicikl;
  $("p-km-pjesice").value = p.max_km.pjesice;
  $("p-max-ducana").value = String(p.max_ducana);
  const lanci = $("p-lanci");
  lanci.replaceChildren();
  for (const [kod, ime] of Object.entries(LANCI)) {
    const k = el("input", { type: "checkbox", value: kod });
    k.checked = p.iskljuceni_lanci.includes(kod);
    lanci.append(el("label", {}, k, ime));
  }
  prikaziGorivoUPostavkama();
  $("postavke").showModal();
}

async function traziKucnuAdresu() {
  const upit = $("p-adresa").value.trim();
  if (upit.length < 3) return;
  $("p-adresa-odabrana").textContent = "Tražim…";
  try {
    const lista = await api("GET", `/api/adresa?q=${encodeURIComponent(upit)}`);
    $("p-adresa-odabrana").textContent = lista.length ? "Odaberi točnu adresu:" : "";
    prikaziAdrese(lista, $("p-adrese"), (a) => {
      odabraniDom = { lat: a.lat, lon: a.lon, adresa: kratkaAdresa(a.adresa) };
      $("p-adrese").replaceChildren();
      $("p-adresa-odabrana").textContent = `Odabrano: ${odabraniDom.adresa} (spremi za potvrdu)`;
    });
  } catch (err) {
    $("p-adresa-odabrana").textContent = "";
    greska(err);
  }
}

function broj_(id, zadano) {
  const v = parseFloat(String($(id).value).replace(",", "."));
  return Number.isFinite(v) ? v : zadano;
}

async function spremiPostavke(e) {
  e.preventDefault();
  const p = stanje.postavke;
  const promjene = {
    gorivo: {
      vrsta: $("p-gorivo").value,
      potrosnja: broj_("p-potrosnja", p.gorivo.potrosnja),
      rucna_cijena: $("p-rucna-cijena").value === "" ? null : broj_("p-rucna-cijena", null),
    },
    racunaj_vrijeme_auto: $("p-vrijeme-auto").checked,
    vrijednost_sata: broj_("p-sat", p.vrijednost_sata),
    max_km: {
      auto: broj_("p-km-auto", p.max_km.auto),
      bicikl: broj_("p-km-bicikl", p.max_km.bicikl),
      pjesice: broj_("p-km-pjesice", p.max_km.pjesice),
    },
    max_ducana: parseInt($("p-max-ducana").value, 10) || 3,
    iskljuceni_lanci: [...$("p-lanci").querySelectorAll("input:checked")].map((k) => k.value),
  };
  const kljuc = $("p-kljuc").value.trim();
  if (kljuc) promjene.api_kljuc = kljuc;
  if (odabraniDom) promjene.dom = odabraniDom;
  try {
    stanje.postavke = await api("PUT", "/api/postavke", promjene);
    $("postavke").close();
    obavijest("Postavke su spremljene.");
    if (odabraniDom && !stanje.polaziste) postaviPocetnuKartu();
    osvjeziSve();
  } catch (err) { greska(err); }
}

// ---------- Pokretanje ----------
function prikaziUpozorenjaPostavki(stanjeServera) {
  for (const o of document.querySelectorAll(".obavijest.postavke")) o.remove();
  if (!stanjeServera.ima_kljuc) {
    obavijest("Za stvarne cijene upiši besplatni API ključ s cijene.dev.",
      { vrsta: "postavke", trajno: true, gumb: { tekst: "Postavke", akcija: otvoriPostavke } });
  }
  if (!stanjeServera.ima_dom) {
    obavijest("Upiši kućnu adresu da znam odakle krećeš.",
      { vrsta: "postavke", trajno: true, gumb: { tekst: "Postavke", akcija: otvoriPostavke } });
  }
}

function osvjeziSve() {
  prikaziNacin();
  prikaziPolaziste();
  prikaziUpozorenjaPostavki({
    ima_kljuc: stanje.demo || stanje.postavke.api_kljuc_postavljen,
    ima_dom: stanje.postavke.dom.lat != null,
  });
}

async function pokreni() {
  try {
    const s = await api("GET", "/api/stanje");
    stanje.demo = s.demo;
    stanje.postavke = s.postavke;
    stanje.nacin = s.postavke.zadnji_nacin || "auto";
    $("demo-oznaka").hidden = !s.demo;
    [stanje.popis, stanje.grupe] = await Promise.all([api("GET", "/api/popis"), api("GET", "/api/grupe")]);
  } catch (err) {
    greska(err);
    return;
  }
  prikaziPopis();
  prikaziZapamceno();
  osvjeziSve();
  inicijalizirajKartu();
  ucitajGorivo();

  $("trazilica").addEventListener("submit", trazi);
  $("zatvori-pretragu").addEventListener("click", zatvoriPretragu);
  $("dodaj-grupu").addEventListener("click", otvoriGrupaDijalog);
  $("grupa-forma").addEventListener("submit", dodajGrupu);
  $("grupa-odustani").addEventListener("click", () => $("grupa-dijalog").close());
  for (const b of document.querySelectorAll(".nacin")) {
    b.addEventListener("click", () => odaberiNacin(b.dataset.nacin));
  }
  $("promijeni-polaziste").addEventListener("click", () => {
    if (stanje.polaziste) {
      stanje.polaziste = null;
      prikaziPolaziste();
      postaviPocetnuKartu();
    } else {
      $("polaziste-forma").hidden = !$("polaziste-forma").hidden;
      if (!$("polaziste-forma").hidden) $("polaziste-upit").focus();
    }
  });
  $("polaziste-forma").addEventListener("submit", traziPolaziste);
  $("moja-lokacija").addEventListener("click", mojaLokacija);
  $("izracunaj").addEventListener("click", izracunaj);
  $("otvori-postavke").addEventListener("click", otvoriPostavke);
  $("postavke-forma").addEventListener("submit", spremiPostavke);
  $("p-zatvori").addEventListener("click", () => $("postavke").close());
  $("p-odustani").addEventListener("click", () => $("postavke").close());
  $("p-trazi-adresu").addEventListener("click", traziKucnuAdresu);
  $("p-adresa").addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); traziKucnuAdresu(); }
  });
  $("p-gorivo").addEventListener("change", prikaziGorivoUPostavkama);
  $("p-osvjezi-gorivo").addEventListener("click", () => ucitajGorivo(true));
}

pokreni();
