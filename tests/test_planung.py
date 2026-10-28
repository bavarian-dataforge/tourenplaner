"""Tests: Der Solver liefert gültige Pläne, der Prüfer findet absichtlich eingebaute Fehler."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fahrzeiten import Fahrzeiten          # noqa: E402
from pruefer import pruefen               # noqa: E402
from solver import planen                 # noqa: E402
from testdaten import baeckerei_nordoberpfalz   # noqa: E402

ZEITLIMIT = 0.5   # Sekunden je Planung - reicht für die kleinen Testfälle


@pytest.fixture(scope="module")
def standard():
    # Standardfall mit 2 s Rechenzeit: Mit 0,5 s findet die Suche hier
    # noch nicht immer einen Plan, der alle 18 Stopps unterbringt.
    problem = baeckerei_nordoberpfalz(seed=7)
    return problem, planen(problem, zeitlimit_s=2.0)


# ------------------------------------------------------------ Solver

@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5, 7, 11])
def test_jeder_plan_besteht_den_pruefer(seed):
    problem = baeckerei_nordoberpfalz(seed=seed)
    plan = planen(problem, zeitlimit_s=ZEITLIMIT)
    assert pruefen(problem, plan) == []


def test_standardfall_alle_stopps_bedient(standard):
    _, plan = standard
    assert plan.offen == []


def test_drei_zeiten_je_stopp_in_richtiger_reihenfolge(standard):
    _, plan = standard
    for t in plan.touren:
        assert t.laden_ab < t.abfahrt_depot
        for ps in t.stopps:
            assert ps.ankunft <= ps.beginn < ps.abfahrt


def test_erst_backen_dann_fahren(standard):
    problem, plan = standard
    for t in plan.touren:
        fertig = max(problem.stopp(ps.stopp_id).fertig_ab for ps in t.stopps)
        assert t.laden_ab >= fertig


def test_zu_wenig_fahrer_gibt_offene_stopps_aber_gueltigen_plan():
    problem = baeckerei_nordoberpfalz(seed=7, fahrer=1)
    plan = planen(problem, zeitlimit_s=ZEITLIMIT)
    assert plan.offen, "mit einem Fahrer sollte nicht alles passen"
    assert pruefen(problem, plan) == []


# ------------------------------------------------------------ Prüfer

def _kaputt(standard):
    problem, plan = standard
    return problem, copy.deepcopy(plan)


def test_pruefer_findet_fensterverletzung(standard):
    problem, plan = _kaputt(standard)
    ps = plan.touren[0].stopps[0]
    ps.beginn = problem.stopp(ps.stopp_id).fenster_bis + 30
    assert any("außerhalb" in f for f in pruefen(problem, plan))


def test_pruefer_findet_doppelten_stopp(standard):
    problem, plan = _kaputt(standard)
    plan.offen.append(plan.touren[0].stopps[0].stopp_id)
    assert any("kommt 2-mal vor" in f for f in pruefen(problem, plan))


def test_pruefer_findet_fehlenden_stopp(standard):
    problem, plan = _kaputt(standard)
    plan.touren[0].stopps.pop()
    assert any("fehlt im Plan" in f for f in pruefen(problem, plan))


def test_pruefer_findet_ueberladenes_fahrzeug(standard):
    problem, plan = _kaputt(standard)
    erste, zweite = plan.touren[0], plan.touren[1]
    erste.stopps.extend(zweite.stopps)       # alle Kisten in ein Fahrzeug
    zweite.stopps.clear()
    assert any("Fahrzeug fasst" in f for f in pruefen(problem, plan))


def test_pruefer_findet_zu_fruehe_abfahrt(standard):
    problem, plan = _kaputt(standard)
    t = plan.touren[0]
    t.laden_ab = problem.fahrer_mit_id(t.fahrer_id).schicht_von   # vor Fertigzeit der Ware
    assert any("Ware erst" in f for f in pruefen(problem, plan))


def test_pruefer_findet_falsch_gerechnete_ankunft(standard):
    problem, plan = _kaputt(standard)
    plan.touren[0].stopps[1].ankunft -= 5
    assert any("nachgerechnet" in f for f in pruefen(problem, plan))


def test_fahrzeiten_symmetrisch_und_null_auf_diagonale():
    fz = Fahrzeiten(baeckerei_nordoberpfalz(seed=7))
    for i in range(5):
        assert fz.minuten(i, i) == 0
        for j in range(5):
            assert fz.minuten(i, j) == fz.minuten(j, i)
