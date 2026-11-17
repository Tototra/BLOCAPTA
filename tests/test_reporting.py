from blocapta.llm import FakeLLM
from blocapta.models import FicheLogiciel
from blocapta.pipeline import run_audit
from blocapta.reporting import ReportNarrative, unverified_numbers
from blocapta.reporting.narrative import generate_narrative


def test_full_audit_without_llm(hospital, fiche):
    r = run_audit(hospital, fiche, days=5, replications=2)
    assert "non déployable" in r.facts.score.level  # NO_GO réglementaire (AIPD)
    assert r.facts.score.confidence == "faible"
    assert "Points de vigilance" in r.markdown
    assert "cardinalite" in r.markdown
    assert r.html.startswith("<!DOCTYPE html>") and "<table>" in r.html


def test_not_analysable_skips_simulation(hospital):
    r = run_audit(hospital, FicheLogiciel(), days=2, replications=1)
    assert r.facts.simulation is None
    assert r.facts.score.score <= 30
    assert "NON_ANALYSABLE" in r.markdown


def test_factcheck():
    facts = {"a": 0.5734, "b": [12.5, "14 h"], "c": 135.66}
    assert unverified_numbers("57,3 % et 12.5 et 14 et 2,26 h", facts) == []
    assert unverified_numbers("perte de 999 heures", facts) == ["999"]


def test_llm_narrative_with_invented_number_is_rejected(hospital, fiche):
    r = run_audit(hospital, fiche, days=3, replications=1)
    invented = ReportNarrative(resume_executif="Le logiciel fera perdre 98765 heures.")
    llm = FakeLLM(structured_handler=lambda p, s: invented)
    n = generate_narrative(r.facts, llm)
    assert n.generated_by == "deterministe"
    assert "98765" in n.unverified_numbers


def test_llm_narrative_accepted_when_grounded(hospital, fiche):
    r = run_audit(hospital, fiche, days=3, replications=1)
    score = r.facts.score.score
    ok = ReportNarrative(resume_executif=f"Score de {score}/100.")
    n = generate_narrative(r.facts, FakeLLM(structured_handler=lambda p, s: ok))
    assert n.generated_by == "llm:fake"


def test_reference_bloc_audit_report_sections(fiche):
    from blocapta.configurator import load_hospital

    ref = load_hospital({"id": "r", "name": "r", "extends": "bloc_reference"})
    r = run_audit(ref, fiche, days=14, replications=1)
    md = r.markdown
    for section in ("Effets humains", "Contrôle de complétude", "Conformité réglementaire", "Paramètres à calibrer", "Hypothèses"):
        assert section in md
    assert len(r.narrative.points_de_vigilance) <= 6  # frictions regroupées par métier
