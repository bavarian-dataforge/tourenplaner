"""Unabhängiger Prüfer: kontrolliert jeden Plan gegen die Regeln.

Er kennt den Solver nicht und vertraut ihm nicht. Er bekommt nur Problem und Plan
und rechnet jede Zeit selbst nach. Leere Liste = Plan ist gültig.

Geprüft wird (wie im Handbuch der KI-Café-Demo):
  * jeder Stopp genau einmal - bedient oder ausdrücklich offen
  * kein Lieferfenster, keine Schicht, kein Fahrzeug überschritten
  * keine Tour fährt los, bevor ihre Ware fertig ist
  * die Touren eines Fahrers überschneiden sich nicht
  * die drei Zeiten je Stopp passen zur Fahrzeitmatrix
"""
from __future__ import annotations

from collections import Counter

from fahrzeiten import Fahrzeiten
from modell import Plan, Problem, uhrzeit


def pruefen(problem: Problem, plan: Plan, fahrzeiten: Fahrzeiten | None = None) -> list[str]:
    fz = fahrzeiten or Fahrzeiten(problem)
    fehler: list[str] = []
    index = {s.id: i for i, s in enumerate(problem.stopps, start=1)}
    lade = problem.betrieb.ladezeit

    # 1. Jeder Stopp genau einmal
    gezaehlt = Counter([ps.stopp_id for t in plan.touren for ps in t.stopps] + plan.offen)
    for sid in index:
        if gezaehlt[sid] == 0:
            fehler.append(f"{sid}: fehlt im Plan (weder bedient noch offen)")
        elif gezaehlt[sid] > 1:
            fehler.append(f"{sid}: kommt {gezaehlt[sid]}-mal vor")
    for sid in gezaehlt:
        if sid not in index:
            fehler.append(f"{sid}: unbekannter Stopp")

    fahrer_ids = {f.id for f in problem.fahrer}
    for t in plan.touren:
        name = f"{t.fahrer_id}/Tour {t.nr}"
        if t.fahrer_id not in fahrer_ids:
            fehler.append(f"{name}: unbekannter Fahrer")
            continue
        f = problem.fahrer_mit_id(t.fahrer_id)
        bekannte = [ps for ps in t.stopps if ps.stopp_id in index]
        if not bekannte:
            fehler.append(f"{name}: leere Tour")
            continue
        stopps = [problem.stopp(ps.stopp_id) for ps in bekannte]

        # 2. Fahrzeug
        summe = sum(s.kisten for s in stopps)
        if summe > f.kapazitaet:
            fehler.append(f"{name}: {summe} Kisten, Fahrzeug fasst {f.kapazitaet}")

        # 3. Beladen und Fertigzeit
        if t.abfahrt_depot - t.laden_ab < lade:
            fehler.append(f"{name}: Beladen kürzer als {lade} Minuten")
        if t.laden_ab < f.schicht_von:
            fehler.append(f"{name}: Beladen {uhrzeit(t.laden_ab)} vor Schichtbeginn")
        fertig = max(s.fertig_ab for s in stopps)
        if t.laden_ab < fertig:
            fehler.append(f"{name}: lädt {uhrzeit(t.laden_ab)}, Ware erst {uhrzeit(fertig)} fertig")

        # 4. Zeiten Stopp für Stopp nachrechnen
        t_ab, vorher = t.abfahrt_depot, 0
        for ps, s in zip(bekannte, stopps):
            k = index[ps.stopp_id]
            erwartet = t_ab + fz.minuten(vorher, k)
            if ps.ankunft != erwartet:
                fehler.append(f"{name}/{s.id}: Ankunft {uhrzeit(ps.ankunft)}, "
                              f"nachgerechnet {uhrzeit(erwartet)}")
            if ps.beginn < ps.ankunft:
                fehler.append(f"{name}/{s.id}: Entladen beginnt vor der Ankunft")
            if not (s.fenster_von <= ps.beginn <= s.fenster_bis):
                fehler.append(f"{name}/{s.id}: Beginn {uhrzeit(ps.beginn)} außerhalb "
                              f"{uhrzeit(s.fenster_von)}-{uhrzeit(s.fenster_bis)}")
            if ps.abfahrt - ps.beginn < s.servicezeit:
                fehler.append(f"{name}/{s.id}: Entladen kürzer als {s.servicezeit} Minuten")
            t_ab, vorher = ps.abfahrt, k
        rueck = t_ab + fz.minuten(vorher, 0)
        if t.rueckkehr != rueck:
            fehler.append(f"{name}: Rückkehr {uhrzeit(t.rueckkehr)}, nachgerechnet {uhrzeit(rueck)}")
        if t.rueckkehr > f.schicht_bis:
            fehler.append(f"{name}: Rückkehr {uhrzeit(t.rueckkehr)} nach Schichtende")

    # 5. Touren eines Fahrers nacheinander, nicht gleichzeitig
    for f in problem.fahrer:
        eigene = sorted((t for t in plan.touren if t.fahrer_id == f.id), key=lambda t: t.laden_ab)
        if len(eigene) > f.max_touren:
            fehler.append(f"{f.id}: {len(eigene)} Touren, erlaubt {f.max_touren}")
        for a, b in zip(eigene, eigene[1:]):
            if b.laden_ab < a.rueckkehr:
                fehler.append(f"{f.id}: Tour {b.nr} lädt vor Rückkehr von Tour {a.nr}")

    return fehler
