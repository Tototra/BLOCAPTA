"""Test de cohérence (cahier des charges, test n° 2) : les effets simulés vont-ils dans le
sens attendu par la littérature ?"""

import pytest
import yaml

from blocapta.configurator import load_hospital
from blocapta.models import SoftwareModel
from blocapta.models.scenario import HumanFactorConfig, Incident, Scenario
from blocapta.simulation import simulate_audit
from blocapta.simulation.human import Agent, HumanLayer
from blocapta.spec import fiche_to_software

from .conftest import EXAMPLES

DAYS, REPS = 15, 2
_CACHE: dict[str, object] = {}


@pytest.fixture(scope="module")
def ref():
    return load_hospital({"id": "r", "name": "r", "extends": "bloc_reference"})


@pytest.fixture(scope="module")
def sw():
    from .conftest import load_fiche

    return fiche_to_software(load_fiche("archivactes"))[0]


def _trust(ref, sw, sc, role, day):
    key = sc.model_dump_json()
    if key not in _CACHE:
        _CACHE[key] = simulate_audit(ref, sw, days=DAYS, replications=REPS, scenario=sc)
    r = _CACHE[key]
    return r.human.trust_by_day[role][day], r


def test_loss_aversion_is_asymmetric():
    layer = HumanLayer(Scenario(name="t"), SoftwareModel(name="x"))
    up, down = Agent("p", 0, "r", 0.5, 1), Agent("p", 1, "r", 0.5, 1)
    layer.update(up, 1.0)
    layer.update(down, 0.0)
    assert (0.5 - down.trust) == pytest.approx(1.955 * (up.trust - 0.5))


def test_learning_curve_decreases(ref, sw):
    layer = HumanLayer(Scenario(name="t"), SoftwareModel(name="x"))
    novice, expert = Agent("p", 0, "r", 0.5, 1), Agent("p", 1, "r", 0.5, 1, tool_uses=60)
    assert layer.learning_factor(novice) == pytest.approx(1.6)
    assert layer.learning_factor(expert) < 1.05
    r = simulate_audit(ref, sw, days=21, replications=1, scenario=Scenario(name="lundi", random_outages=False))
    weeks = r.human.sw_minutes_by_week
    assert weeks[0] > weeks[2]


def test_early_outage_lowers_trust_durably_and_support_helps(ref, sw):
    calm = Scenario(name="calme", random_outages=False)
    crash = Scenario(name="panne", random_outages=False, incidents=[Incident(day=1, at="09:00", duration_min=120)])
    helped = crash.model_copy(update={"name": "support", "support_on_site_days": 5})
    t_calm, _ = _trust(ref, sw, calm, "iade", 10)
    t_crash, _ = _trust(ref, sw, crash, "iade", 10)
    t_help, _ = _trust(ref, sw, helped, "iade", 10)
    assert t_crash < t_calm
    assert t_crash < t_help <= t_calm + 1e-9


def test_sceptic_slows_team_and_champion_compensates(ref, sw):
    sc = Scenario.model_validate(yaml.safe_load((EXAMPLES / "scenarios" / "chirurgien_sceptique.yaml").read_text()))
    ch = Scenario.model_validate(yaml.safe_load((EXAMPLES / "scenarios" / "champion.yaml").read_text()))
    calm = Scenario(name="calme", human=HumanFactorConfig(kappa=0.08))
    t_calm, _ = _trust(ref, sw, calm, "chir_orthopedie", 7)
    t_sc, r = _trust(ref, sw, sc, "chir_orthopedie", 7)
    assert t_sc < t_calm
    ib_sc = r.human.trust_by_day["ibode"][14]
    _, r2 = _trust(ref, sw, ch, "chir_orthopedie", 7)
    assert r2.human.trust_by_day["ibode"][14] > ib_sc
    assert any("réticent" in k for k in r.human.special_agents)


def test_deployment_day_respected(ref, sw):
    late = Scenario(name="tard", deployment_day=7, random_outages=False)
    r = simulate_audit(ref, sw, days=7, replications=1, scenario=late)
    assert not r.frictions  # outil jamais utilisé avant son déploiement
