"""Erfundener Testbetrieb "Bäckerei Nordoberpfalz".

Keine echten Filialen, keine echten Kunden: Die Punkte werden mit festem Seed
zufällig um eine erfundene Backstube verteilt (Ringe von 3 bis 40 km).
Gleicher Seed -> gleiche Daten, damit Tests reproduzierbar sind.
"""
from __future__ import annotations

import math
import random

from modell import Betrieb, Fahrer, Problem, Stopp, minuten

DEPOT_LAT, DEPOT_LON = 49.90, 12.05   # erfunden

# Erfundene Ortsnamen, bewusst ohne Bezug zu echten Filialnetzen
ORTE = ["Lindenau", "Steinbach", "Föhrenried", "Hammerthal", "Birkenhöhe", "Mühlgrund",
        "Eichenbrunn", "Kirchdorf", "Wiesenau", "Tannfeld", "Brunnhof", "Schönwald-Ost",
        "Rabenstein", "Erlengrund", "Moosbach", "Haidberg", "Seeleiten", "Kalkreuth"]

# Feste Hinweise, wie sie in Stammdaten stehen (bei echten Kunden: anonymisieren!)
HINWEISE = ["Anlieferung über den Hintereingang", "Schlüsselbox links neben der Tür",
            "Kühlware direkt in den Kühlraum", "Rampe hinten, bitte rückwärts anfahren",
            "Klingel B, vor 6 Uhr nicht klingeln"]


def _punkt(rng: random.Random, min_km: float, max_km: float) -> tuple[float, float]:
    r = rng.uniform(min_km, max_km)
    w = rng.uniform(0, 2 * math.pi)
    dlat = r * math.cos(w) / 111.32
    dlon = r * math.sin(w) / (111.32 * math.cos(math.radians(DEPOT_LAT)))
    return round(DEPOT_LAT + dlat, 5), round(DEPOT_LON + dlon, 5)


def baeckerei_nordoberpfalz(seed: int = 7, filialen: int = 14, gastro: int = 4,
                            fahrer: int = 3) -> Problem:
    rng = random.Random(seed)
    # Eigener Zufallsgenerator für Namen und Hinweise: So ändern sich Orte,
    # Mengen und Zeiten nicht, nur weil Namen dazugekommen sind.
    rng_text = random.Random(seed + 1000)
    anzahl = filialen + gastro
    orte = rng_text.sample(ORTE, k=min(anzahl, len(ORTE)))
    orte += [f"Ort {n:02d}" for n in range(len(orte) + 1, anzahl + 1)]   # falls mehr Stopps als Namen

    def hinweis() -> str:
        return rng_text.choice(HINWEISE) if rng_text.random() < 0.3 else ""

    stopps: list[Stopp] = []

    # Filialen: öffnen um 6:00, Ware muss vorher da sein. Brot früh fertig.
    for i in range(1, filialen + 1):
        lat, lon = _punkt(rng, 3, 40)
        stopps.append(Stopp(
            id=f"F{i:02d}", name=f"Filiale {i:02d}", lat=lat, lon=lon,
            kisten=rng.randint(15, 40),
            fenster_von=minuten("03:30"), fenster_bis=minuten("05:45"),
            servicezeit=rng.randint(8, 12),
            fertig_ab=rng.choice([minuten("02:15"), minuten("02:30"), minuten("02:45")]),
            art="Filiale", ort=orte[i - 1], hinweis=hinweis(),
        ))

    # Gastro-Kunden: später am Morgen, Snacks werden erst ab 5 Uhr fertig.
    for i in range(1, gastro + 1):
        lat, lon = _punkt(rng, 3, 25)
        von = rng.choice([minuten("06:30"), minuten("07:00")])
        stopps.append(Stopp(
            id=f"G{i:02d}", name=f"Kantine {i:02d}", lat=lat, lon=lon,
            kisten=rng.randint(5, 15),
            fenster_von=von, fenster_bis=von + 120,
            servicezeit=5,
            fertig_ab=minuten("05:00"),
            art="Gastro", ort=orte[filialen + i - 1], hinweis=hinweis(),
        ))

    fahrer_liste = tuple(
        Fahrer(id=f"P{i}", name=f"Fahrer {i}",
               schicht_von=minuten("02:00"), schicht_bis=minuten("11:00"),
               kapazitaet=160, max_touren=3)
        for i in range(1, fahrer + 1)
    )
    betrieb = Betrieb(name="Bäckerei Nordoberpfalz (erfunden)",
                      depot_lat=DEPOT_LAT, depot_lon=DEPOT_LON)
    return Problem(betrieb=betrieb, stopps=tuple(stopps), fahrer=fahrer_liste)
