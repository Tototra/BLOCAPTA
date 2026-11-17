import pytest

from blocapta.calibration import build_pathway, generate_bloc_log
from blocapta.models import Hospital
from blocapta.models.distributions import Fixed
from blocapta.models.hospital import TimeWindow
from blocapta.simulation import Simulation, SimulationOptions, simulate_audit, validate_twin
from blocapta.simulation.engine import off_periods


def test_off_periods_day_shift():
    w = TimeWindow(start="08:00", end="18:00", weekdays=[0])
    periods = off_periods(w, 2 * 1440)
    assert periods[0] == (0, 480)
    assert periods[1] == (1080, 2880)


def test_night_window_contains():
    w = TimeWindow(start="20:00", end="08:00", weekdays=[0])
    assert w.contains(21 * 60)  # lundi 21h
    assert w.contains(1440 + 7 * 60)  # mardi 7h (nuit de lundi)
    assert not w.contains(1440 + 21 * 60)  # mardi 21h


def test_baseline_has_no_friction(hospital):
    r = Simulation(hospital, None, SimulationOptions(days=5, seed=1)).run()
    assert r.frictions == []
    assert r.kpis["patients_termines"] > 0


def test_reproducible(hospital, software):
    a = Simulation(hospital, software, SimulationOptions(days=5, seed=3)).run().kpis
    b = Simulation(hospital, software, SimulationOptions(days=5, seed=3)).run().kpis
    assert a == b


def test_surgeon_case_detects_cardinality(hospital, software):
    """Le cas réel : outil limité à 1 acte par saisie, plusieurs actes par intervention."""
    report = simulate_audit(hospital, software, days=10, replications=3)
    types = {f.type for f in report.frictions}
    assert "cardinalite" in types
    card = next(f for f in report.frictions if f.type == "cardinalite")
    assert 0.4 < card.affected_share < 0.7  # 55 % des interventions ont ≥ 2 actes
    doc = next(k for k in report.kpis if k.kpi == "temps_documentation_h.chirurgien")
    assert doc.software.mean > doc.baseline.mean


def test_unlimited_software_has_no_cardinality_friction(hospital, software):
    sw = software.model_copy(deep=True)
    sw.touchpoints[0].max_items_per_entry = None
    report = simulate_audit(hospital, sw, days=5, replications=2)
    assert "cardinalite" not in {f.type for f in report.frictions}


def test_interface_to_dpi_removes_double_entry(hospital, software):
    sw = software.model_copy(deep=True)
    sw.interfaces.append(sw.interfaces[0].model_copy(update={"target_category": "DPI"}))
    report = simulate_audit(hospital, sw, days=5, replications=2)
    assert "interoperabilite" not in {f.type for f in report.frictions}


def test_role_not_supported(hospital, software):
    sw = software.model_copy(deep=True)
    sw.touchpoints[0].roles = ["ibode"]
    report = simulate_audit(hospital, sw, days=5, replications=2)
    assert {f.type for f in report.frictions} == {"couverture"}


def test_concurrency_limit(hospital, software):
    sw = software.model_copy(deep=True)
    sw.max_concurrent_users = 1
    sw.touchpoints[0].time_per_entry_min = Fixed(value=20)
    report = simulate_audit(hospital, sw, days=5, replications=2)
    assert "charge" in {f.type for f in report.frictions}


def test_static_findings(hospital, software):
    report = simulate_audit(hospital, software, days=2, replications=1)
    severities = {s.severity for s in report.static_findings if s.type == "interoperabilite"}
    assert "critique" in severities


def test_twin_validation_on_calibrated_pathway():
    df = generate_bloc_log(days=40, cases_per_day=20, seed=5)
    pw, cal = build_pathway(df, "chir", "bloc")
    h = Hospital(
        id="test", name="test", services={"bloc": {"label": "Bloc"}}, pathways=[pw],
    )
    v = validate_twin(h, [cal], days=20, replications=5, tolerance_pct=15)
    assert v.valid, v.rows


@pytest.mark.parametrize("workers", [2])
def test_parallel_runs_match_sequential(hospital, software, workers):
    from blocapta.simulation import run_replications

    opts = SimulationOptions(days=3, seed=9)
    seq = run_replications(hospital, software, opts, 2, workers=1)
    par = run_replications(hospital, software, opts, 2, workers=workers)
    assert [r.kpis for r in seq] == [r.kpis for r in par]
