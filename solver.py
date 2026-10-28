"""Tourenplanung mit Google OR-Tools (Vehicle Routing Problem mit Zeitfenstern).

Arbeitsteilung:
  * OR-Tools entscheidet, WER welche Stopps in WELCHER Reihenfolge fährt.
  * Die Uhrzeiten rechnen wir danach selbst vorwärts aus (_zeitplan). Das ist
    einfacher nachzuvollziehen und liefert genau die drei Zeiten je Stopp,
    die Fahrer-Handy und Zeitstrahl brauchen.

Modellierung der Mehrfachtouren: Jeder Fahrer bekommt max_touren "Tour-Slots".
Jeder Slot ist für OR-Tools ein eigenes Fahrzeug. Eine Nebenbedingung sorgt dafür,
dass Slot k erst startet, wenn Slot k-1 zurück ist und neu beladen wurde.
"""
from __future__ import annotations

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from fahrzeiten import Fahrzeiten
from modell import Fahrer, Plan, PlanStopp, Problem, Tour

HORIZONT = 24 * 60          # ein Tag in Minuten
STRAFE_OFFEN = 100_000      # "Kosten" eines nicht bedienten Stopps (sehr teuer)
FIXKOSTEN_TOUR = 30         # jede zusätzliche Tour kostet etwas -> weniger Touren


def planen(problem: Problem, fahrzeiten: Fahrzeiten | None = None,
           zeitlimit_s: float = 2.0) -> Plan:
    fz = fahrzeiten or Fahrzeiten(problem)
    n = len(problem.stopps)
    lade = problem.betrieb.ladezeit

    slots: list[tuple[Fahrer, int]] = [(f, k) for f in problem.fahrer for k in range(f.max_touren)]
    if not slots or n == 0:
        return Plan(touren=[], offen=[s.id for s in problem.stopps])

    manager = pywrapcp.RoutingIndexManager(n + 1, len(slots), 0)   # Knoten 0 = Backstube
    routing = pywrapcp.RoutingModel(manager)
    knoten = manager.IndexToNode

    service = [0] + [s.servicezeit for s in problem.stopps]
    kisten = [0] + [s.kisten for s in problem.stopps]

    # --- Kosten: reine Fahrzeit (Minuten) -------------------------------------
    fahr_cb = routing.RegisterTransitCallback(lambda i, j: fz.minuten(knoten(i), knoten(j)))
    routing.SetArcCostEvaluatorOfAllVehicles(fahr_cb)
    routing.SetFixedCostOfAllVehicles(FIXKOSTEN_TOUR)

    # --- Zeit: Entladen am Startknoten + Fahrt zum nächsten -------------------
    zeit_cb = routing.RegisterTransitCallback(
        lambda i, j: service[knoten(i)] + fz.minuten(knoten(i), knoten(j)))
    # slack_max = HORIZONT: Warten vor einem Kunden ist erlaubt
    routing.AddDimension(zeit_cb, HORIZONT, HORIZONT, False, "Zeit")
    zeit = routing.GetDimensionOrDie("Zeit")

    # --- Kapazität: Kisten je Tour ---------------------------------------------
    kisten_cb = routing.RegisterUnaryTransitCallback(lambda i: kisten[knoten(i)])
    routing.AddDimensionWithVehicleCapacity(
        kisten_cb, 0, [f.kapazitaet for f, _ in slots], True, "Kisten")

    # --- Lieferfenster und "darf offen bleiben" --------------------------------
    for nr, s in enumerate(problem.stopps, start=1):
        idx = manager.NodeToIndex(nr)
        zeit.CumulVar(idx).SetRange(s.fenster_von, s.fenster_bis)   # Cumul = Beginn Entladen
        routing.AddDisjunction([idx], STRAFE_OFFEN)

    # --- Schicht, Tourfolge, Fertigzeiten --------------------------------------
    solver = routing.solver()
    for v, (f, k) in enumerate(slots):
        start = zeit.CumulVar(routing.Start(v))   # = Abfahrt an der Backstube
        ende = zeit.CumulVar(routing.End(v))      # = Rückkehr
        start.SetMin(f.schicht_von + lade)
        ende.SetMax(f.schicht_bis)
        if k > 0:   # Slot k erst nach Rückkehr von Slot k-1 plus Beladen
            solver.Add(start >= zeit.CumulVar(routing.End(v - 1)) + lade)
        routing.AddVariableMinimizedByFinalizer(ende)
        # "Erst backen, dann fahren": Liegt Stopp s auf dieser Tour,
        # darf sie frühestens fertig_ab + Ladezeit abfahren.
        for nr, s in enumerate(problem.stopps, start=1):
            auf_dieser_tour = solver.IsEqualCstVar(routing.VehicleVar(manager.NodeToIndex(nr)), v)
            solver.Add(start >= (s.fertig_ab + lade) * auf_dieser_tour)

    # --- Suche ------------------------------------------------------------------
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(int(zeitlimit_s * 1000))

    loesung = routing.SolveWithParameters(params)
    if loesung is None:
        return Plan(touren=[], offen=[s.id for s in problem.stopps])

    # --- Reihenfolgen auslesen -------------------------------------------------
    reihenfolgen: dict[str, list[list[int]]] = {f.id: [] for f in problem.fahrer}
    for v, (f, _) in enumerate(slots):
        idx = loesung.Value(routing.NextVar(routing.Start(v)))
        folge = []
        while not routing.IsEnd(idx):
            folge.append(knoten(idx))
            idx = loesung.Value(routing.NextVar(idx))
        if folge:
            reihenfolgen[f.id].append(folge)

    offen = [s.id for nr, s in enumerate(problem.stopps, start=1)
             if loesung.Value(routing.NextVar(manager.NodeToIndex(nr))) == manager.NodeToIndex(nr)]

    touren: list[Tour] = []
    for f in problem.fahrer:
        touren.extend(_zeitplan(problem, fz, f, reihenfolgen[f.id]))
    return Plan(touren=touren, offen=offen)


def _zeitplan(problem: Problem, fz: Fahrzeiten, f: Fahrer,
              folgen: list[list[int]]) -> list[Tour]:
    """Rechnet für die Touren eines Fahrers die Uhrzeiten vorwärts aus.

    Abfahrt so früh wie möglich (Schicht, Fertigzeit, Rückkehr der Vortour),
    danach um die Wartezeit am ersten Stopp nach hinten geschoben: Der Fahrer
    steht dann nicht unnötig vor verschlossener Tür, die Rückkehr bleibt gleich.
    """
    lade = problem.betrieb.ladezeit
    touren: list[Tour] = []
    frei_ab = f.schicht_von                      # wann darf das nächste Beladen beginnen
    for nr, folge in enumerate(folgen, start=1):
        stopps = [problem.stopps[k - 1] for k in folge]
        abfahrt = max(frei_ab + lade, max(s.fertig_ab for s in stopps) + lade)

        # Wartezeit am ersten Stopp abziehen (Start später, Rest unverändert)
        erste_ankunft = abfahrt + fz.minuten(0, folge[0])
        abfahrt += max(0, stopps[0].fenster_von - erste_ankunft)

        plan_stopps: list[PlanStopp] = []
        t, vorher, km = abfahrt, 0, 0.0
        for k, s in zip(folge, stopps):
            ankunft = t + fz.minuten(vorher, k)
            beginn = max(ankunft, s.fenster_von)
            ende = beginn + s.servicezeit
            plan_stopps.append(PlanStopp(s.id, ankunft, beginn, ende))
            km += fz.km(vorher, k)
            t, vorher = ende, k
        rueckkehr = t + fz.minuten(vorher, 0)
        km += fz.km(vorher, 0)

        touren.append(Tour(
            fahrer_id=f.id, nr=nr, laden_ab=abfahrt - lade, abfahrt_depot=abfahrt,
            rueckkehr=rueckkehr, stopps=plan_stopps,
            kisten=sum(s.kisten for s in stopps), km=round(km, 1)))
        frei_ab = rueckkehr
    return touren
