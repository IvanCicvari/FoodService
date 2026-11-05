"""Dohvat podataka s interneta (samo standardna Python biblioteka)."""

from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = "GdjeKupiti/0.1 (osobna aplikacija za usporedbu cijena)"


class GreskaMreze(Exception):
    """Vanjski servis nije dostupan ili je vratio grešku."""


def dohvati(url: str, zaglavlja: dict | None = None, timeout: float = 20.0) -> bytes:
    h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if zaglavlja:
        h.update(zaglavlja)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as odg:
            podaci = odg.read()
            if odg.headers.get("Content-Encoding") == "gzip":
                podaci = gzip.decompress(podaci)
            return podaci
    except urllib.error.HTTPError as e:
        tijelo = e.read()[:300].decode("utf-8", "replace")
        raise GreskaMreze(f"{urllib.parse.urlsplit(url).netloc} je vratio HTTP {e.code}: {tijelo}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GreskaMreze(f"Ne mogu dohvatiti {urllib.parse.urlsplit(url).netloc}: {e}") from e


def dohvati_json(url: str, zaglavlja: dict | None = None, timeout: float = 20.0):
    podaci = dohvati(url, zaglavlja, timeout)
    try:
        return json.loads(podaci.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise GreskaMreze(f"Odgovor s {urllib.parse.urlsplit(url).netloc} nije ispravan JSON") from e


def s_parametrima(url: str, **parametri) -> str:
    cisti = {k: v for k, v in parametri.items() if v is not None and v != ""}
    if not cisti:
        return url
    return url + ("&" if "?" in url else "?") + urllib.parse.urlencode(cisti)
