"""Datenmodell der Tourenplanung.

Alle Uhrzeiten sind Minuten seit Mitternacht (03:30 Uhr = 210).
So rechnet der Solver mit ganzen Zahlen; erst die Ausgabe macht daraus "03:30".
"""
from __future__ import annotations

from dataclasses import dataclass, field


def uhrzeit(minuten: int) -> str:
    """210 -> '03:30'"""
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


def minuten(text: str) -> int:
    """'03:30' -> 210"""
    h, m = text.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- Eingabe

@dataclass(frozen=True)
class Betrieb:
    name: str
    depot_lat: float
    depot_lon: float
    ladezeit: int = 15                 # Minuten Beladen vor jeder Tour
    umweg_faktor: float = 1.3          # Luftlinie -> Straße (bis OSRM da ist)
    geschwindigkeit_kmh: float = 50.0  # Durchschnitt inkl. Ortsdurchfahrten


@dataclass(frozen=True)
class Stopp:
    id: str
    name: str
    lat: float
    lon: float
    kisten: int
    fenster_von: int    # frühester Beginn des Entladens
    fenster_bis: int    # spätester Beginn des Entladens
    servicezeit: int    # Minuten für Entladen
    fertig_ab: int      # Ware ist ab dann ladebereit ("erst backen, dann fahren")
    art: str = "Filiale"


@dataclass(frozen=True)
class Fahrer:
    id: str
    name: str
    schicht_von: int
    schicht_bis: int
    kapazitaet: int      # Kisten je Tour
    max_touren: int = 3


@dataclass(frozen=True)
class Problem:
    betrieb: Betrieb
    stopps: tuple[Stopp, ...]
    fahrer: tuple[Fahrer, ...]

    def stopp(self, stopp_id: str) -> Stopp:
        return next(s for s in self.stopps if s.id == stopp_id)

    def fahrer_mit_id(self, fahrer_id: str) -> Fahrer:
        return next(f for f in self.fahrer if f.id == fahrer_id)


# ---------------------------------------------------------------- Ausgabe
# Jeder Stopp trägt drei Zeiten. Fahrer-Handy und Zeitstrahl lesen nur daraus.

@dataclass
class PlanStopp:
    stopp_id: str
    ankunft: int    # Fahrzeug steht vor der Tür
    beginn: int     # Entladen beginnt (>= Ankunft, im Fenster)
    abfahrt: int    # Entladen fertig, weiter zum nächsten Ziel


@dataclass
class Tour:
    fahrer_id: str
    nr: int
    laden_ab: int        # Beladen beginnt
    abfahrt_depot: int   # Fahrzeug verlässt die Backstube
    rueckkehr: int       # Fahrzeug wieder an der Backstube
    stopps: list[PlanStopp]
    kisten: int
    km: float


@dataclass
class Plan:
    touren: list[Tour]
    offen: list[str] = field(default_factory=list)   # Stopp-IDs ohne Platz im Plan

    def kennzahlen(self) -> dict:
        bedient = sum(len(t.stopps) for t in self.touren)
        return {
            "stopps_bedient": bedient,
            "stopps_offen": len(self.offen),
            "touren": len(self.touren),
            "km": round(sum(t.km for t in self.touren), 1),
            "letzte_rueckkehr": uhrzeit(max((t.rueckkehr for t in self.touren), default=0)),
        }
