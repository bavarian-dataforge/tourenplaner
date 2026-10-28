"""Kommandozeile: Testdaten erzeugen, planen, prüfen, ausgeben.

Beispiele:
    python main.py                      # Standarddaten, 3 Fahrer
    python main.py --seed 3 --fahrer 2  # andere Daten, nur 2 Fahrer
    python main.py --json plan.json     # Plan zusätzlich als JSON speichern
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict

from fahrzeiten import Fahrzeiten
from modell import uhrzeit
from pruefer import pruefen
from solver import planen
from testdaten import baeckerei_nordoberpfalz


def main() -> int:
    ap = argparse.ArgumentParser(description="Tourenplanung Bäckerei Nordoberpfalz (erfunden)")
    ap.add_argument("--seed", type=int, default=7, help="Zufalls-Seed der Testdaten")
    ap.add_argument("--fahrer", type=int, default=3, help="Anzahl Fahrer")
    ap.add_argument("--zeitlimit", type=float, default=2.0, help="Rechenzeit des Solvers in Sekunden")
    ap.add_argument("--json", metavar="DATEI", help="Plan als JSON speichern")
    args = ap.parse_args()

    problem = baeckerei_nordoberpfalz(seed=args.seed, fahrer=args.fahrer)
    fz = Fahrzeiten(problem)

    t0 = time.perf_counter()
    plan = planen(problem, fz, zeitlimit_s=args.zeitlimit)
    dauer = time.perf_counter() - t0

    print(f"{problem.betrieb.name} · {len(problem.stopps)} Stopps · {len(problem.fahrer)} Fahrer")
    print(f"gerechnet in {dauer:.1f} s\n")

    for f in problem.fahrer:
        eigene = [t for t in plan.touren if t.fahrer_id == f.id]
        print(f"{f.name}  (Schicht {uhrzeit(f.schicht_von)}–{uhrzeit(f.schicht_bis)})")
        if not eigene:
            print("  keine Tour\n")
            continue
        for t in eigene:
            print(f"  Tour {t.nr} · Laden {uhrzeit(t.laden_ab)} · los {uhrzeit(t.abfahrt_depot)}"
                  f" · zurück {uhrzeit(t.rueckkehr)} · {t.kisten} Kisten · {t.km:.0f} km")
            for ps in t.stopps:
                s = problem.stopp(ps.stopp_id)
                warten = f"  (wartet {ps.beginn - ps.ankunft} min)" if ps.beginn > ps.ankunft else ""
                print(f"    {uhrzeit(ps.ankunft)} an · {uhrzeit(ps.beginn)}–{uhrzeit(ps.abfahrt)}"
                      f"  {s.name:<11} {s.kisten:>3} Kisten · Fenster "
                      f"{uhrzeit(s.fenster_von)}–{uhrzeit(s.fenster_bis)}{warten}")
        print()

    k = plan.kennzahlen()
    print(f"Bedient {k['stopps_bedient']} · offen {k['stopps_offen']} · {k['touren']} Touren"
          f" · {k['km']} km (geschätzt) · letzte Rückkehr {k['letzte_rueckkehr']}")
    if plan.offen:
        print("Offen: " + ", ".join(plan.offen))

    fehler = pruefen(problem, plan, fz)
    print("Prüfer: OK – alle Regeln eingehalten" if not fehler else "Prüfer: FEHLER")
    for z in fehler:
        print("  - " + z)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"kennzahlen": k, **asdict(plan)}, fh, ensure_ascii=False, indent=2)
        print(f"Plan gespeichert: {args.json}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
