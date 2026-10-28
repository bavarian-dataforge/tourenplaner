"""Fahrzeit- und Distanzmatrix.

Index 0 ist die Backstube, Index 1..n sind die Stopps in Reihenfolge von problem.stopps.

Heute: Luftlinie x Umwegfaktor, wie in der KI-Café-Demo.
Später: dieselbe Schnittstelle, gefüllt aus OSRM (/table-Abfrage). Solver und Prüfer
merken davon nichts, sie fragen nur minuten(i, j) und km(i, j).
"""
from __future__ import annotations

import math

from modell import Problem

ERDRADIUS_KM = 6371.0


def luftlinie_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Großkreis-Entfernung (Haversine-Formel)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * ERDRADIUS_KM * math.asin(math.sqrt(a))


class Fahrzeiten:
    def __init__(self, problem: Problem):
        b = problem.betrieb
        punkte = [(b.depot_lat, b.depot_lon)] + [(s.lat, s.lon) for s in problem.stopps]
        n = len(punkte)
        self._km = [[0.0] * n for _ in range(n)]
        self._min = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                km = luftlinie_km(*punkte[i], *punkte[j]) * b.umweg_faktor
                self._km[i][j] = km
                # aufrunden: lieber eine Minute zu viel als zu spät beim Kunden
                self._min[i][j] = math.ceil(km / b.geschwindigkeit_kmh * 60)

    def minuten(self, i: int, j: int) -> int:
        return self._min[i][j]

    def km(self, i: int, j: int) -> float:
        return self._km[i][j]
