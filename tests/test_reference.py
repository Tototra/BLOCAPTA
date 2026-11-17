import pytest

from blocapta.configurator import load_hospital
from blocapta.models.distributions import Quantiles
from blocapta.reference import build_reference_bloc, fidelity_targets, load_stats
from blocapta.simulation import Simulation, SimulationOptions, check_fidelity


@pytest.fixture(scope="module")
def ref():
    return load_hospital({"id": "ref", "name": "ref", "extends": "bloc_reference"})


def test_stats_are_anonymous():
    text = str(load_stats())
    assert "Chirurgien" not in text and "Anesthésiste" not in text


def test_generated_archetype_matches_builder(ref):
    built = build_reference_bloc()
    assert len(ref.pathways) == len(built["pathways"])
    assert ref.programme is not None and ref.programme.fill_ratio == built["programme"]["fill_ratio"]


def test_quantiles_distribution():
    import numpy as np

    q = Quantiles(points={0: 10, 0.5: 20, 1: 40})
    xs = [q.sample(np.random.default_rng(i)) for i in range(2000)]
    assert 18 < np.median(xs) < 22 and min(xs) >= 10 and max(xs) <= 40
    assert q.mean_value() == pytest.approx(22.5)


def test_invariants_and_staff_following_rooms(ref):
    k = Simulation(ref, None, SimulationOptions(days=14, seed=3)).run().kpis
    assert k["controle_ubiquite"] == 0
    assert k["durees_negatives"] == 0
    assert 0 < k["occupation_salles_pct"] <= 100
    assert k["cas_deprogrammes"] <= 5


def test_common_random_numbers(ref):
    a = Simulation(ref, None, SimulationOptions(days=7, seed=5)).run().kpis
    b = Simulation(ref, None, SimulationOptions(days=7, seed=5)).run().kpis
    assert a == b


def test_fidelity_go(ref):
    r = check_fidelity(ref, fidelity_targets(), days=56, replications=6, seed=7)
    assert r.invariants_ok
    assert r.verdict == "GO", [x for x in r.rows if not x.ok]
