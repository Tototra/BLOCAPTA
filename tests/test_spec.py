from pathlib import Path

from blocapta.llm import FakeLLM
from blocapta.models import SoftwareModel, SpecSheet
from blocapta.spec import load_criteria, validate_document, validate_spec
from blocapta.spec.rules import Condition, evaluate_condition, resolve

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_resolve_flatten():
    data = {"a": {"b": [{"c": 1}, {"c": 2}, {}]}}
    assert resolve(data, "a.b[].c") == [1, 2]
    assert evaluate_condition(data, Condition(path="a.b[].c", op="present", mode="any"))


def test_each_mode_fails_when_one_missing():
    data = {"m": {"p": [{"x": 1}, {"x": None}]}}
    assert not evaluate_condition(data, Condition(path="m.p[].x", op="present", mode="each"))


def test_empty_spec_is_not_admissible():
    v = validate_spec(SpecSheet())
    assert not v.admissible
    assert v.score < 20
    assert any(r.id == "REG-01" for r in v.blocking_failures)


def test_example_spec_admissible_with_warnings():
    v = validate_document(EXAMPLES / "specs" / "archivactes.yaml", llm=None)
    assert v.admissible
    failed = {r.id for r in v.results if r.status == "echec"}
    assert "TEC-02" in failed  # pas de mode dégradé
    assert "REG-04" not in failed  # non applicable (pas un DM)


def test_conversion_to_software_model():
    v = validate_document(EXAMPLES / "specs" / "archivactes.yaml", llm=None)
    sw = SoftwareModel.from_spec_sheet(v.spec)
    tp = sw.touchpoints[0]
    assert tp.max_items_per_entry == 1
    assert tp.requires_fixed_workstation
    assert sw.availability is not None and sw.availability.start == "07:00"


def test_free_text_uses_llm_extraction():
    structured = validate_document(EXAMPLES / "specs" / "archivactes.yaml", llm=None).spec

    def handler(prompt, schema):
        if schema is SpecSheet:
            return structured
        return {"items": [{"champ": "technique.mode_degrade", "question": "Existe-t-il un mode dégradé ?"}]}

    llm = FakeLLM(structured_handler=handler)
    v = validate_document(EXAMPLES / "specs" / "archivactes_brochure.txt", llm=llm)
    assert v.admissible
    assert any("mode dégradé" in q.question for q in v.questions)


def test_criteria_file_loads():
    assert len(load_criteria().criteria) >= 15
