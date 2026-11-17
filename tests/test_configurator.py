import json

import pytest

from blocapta.configurator import (
    ConfigPatch,
    PatchOp,
    apply_answers,
    apply_patch,
    deep_merge,
    list_archetypes,
    load_hospital,
    load_hospital_dict,
    load_questionnaire,
    propose_patch,
    render_markdown,
)
from blocapta.configurator.questionnaire import apply_answers_file, transform_value
from blocapta.llm import FakeLLM

from .conftest import EXAMPLES


def test_deep_merge_by_id_and_delete():
    base = {"a": {"x": 1, "y": 2}, "l": [{"id": "p", "v": 1}, {"id": "q", "v": 2}]}
    over = {"a": {"y": {"__delete__": True}}, "l": [{"id": "p", "v": 9}, {"id": "q", "__delete__": True}, {"id": "r"}]}
    out = deep_merge(base, over)
    assert out == {"a": {"x": 1}, "l": [{"id": "p", "v": 9}, {"id": "r"}]}


@pytest.mark.parametrize("name", ["ch_general", "chu", "clinique_privee"])
def test_all_archetypes_load(name):
    h = load_hospital({"id": "t", "name": "t", "extends": name})
    assert h.pathways


def test_archetype_listing():
    assert {"ch_general", "chu", "clinique_privee"} <= set(list_archetypes())


def test_example_hospital_inherits():
    h = load_hospital(EXAMPLES / "hospitals" / "ch_exemple.yaml")
    assert h.resources["salle_bloc"].count == 7
    assert h.resources["ibode"].count == 12  # hérité
    step = next(s for s in h.pathways[0].steps if s.id == "intervention")
    assert step.resources["chirurgien"] == 1  # hérité malgré la surcharge de documentation


def test_patch_with_id_selector():
    cfg = load_hospital_dict({"id": "t", "name": "t", "extends": "ch_general"})
    r = apply_patch(
        cfg,
        [
            PatchOp(op="replace", path="/resources/chirurgien/count", value_json="14"),
            PatchOp(
                op="replace",
                path="/pathways[id=chirurgie_programmee]/steps[id=intervention]/duration_min",
                value_json=json.dumps({"dist": "lognormal", "mean": 100, "sd": 30}),
            ),
        ],
    )
    assert r.ok, r.errors
    assert any("chirurgien/count" in d for d in r.diff)


def test_invalid_patch_rejected():
    cfg = load_hospital_dict({"id": "t", "name": "t", "extends": "ch_general"})
    r = apply_patch(cfg, [PatchOp(op="replace", path="/resources/chirurgien/count", value_json="0")])
    assert not r.ok  # l'étape intervention demande 1 chirurgien


def test_llm_assistant_retries_until_valid():
    cfg = load_hospital_dict({"id": "t", "name": "t", "extends": "ch_general"})
    answers = iter(
        [
            ConfigPatch(operations=[PatchOp(op="replace", path="/resources/inexistant/count", value_json="3")]),
            ConfigPatch(
                rationale="2 salles en plus",
                hypotheses=["mêmes horaires"],
                operations=[PatchOp(op="replace", path="/resources/salle_bloc/count", value_json="10")],
            ),
        ]
    )
    llm = FakeLLM(structured_handler=lambda p, s: next(answers))
    patch, result = propose_patch(cfg, "On ouvre 2 salles de plus", llm)
    assert result.ok and result.config["resources"]["salle_bloc"]["count"] == 10
    assert len(llm.calls) == 2


def test_transforms():
    assert transform_value("time_window", "7h30 - 19h") == {"start": "07:30", "end": "19:00"}
    assert transform_value("weekdays", "lun-ven") == [0, 1, 2, 3, 4]
    assert transform_value("bool", "oui") is True
    assert transform_value("empirical", "{1: 0.5, 2: 0.5}")["values"] == {"1.0": 0.5, "2.0": 0.5}


def test_questionnaire_render():
    q = load_questionnaire()
    md = render_markdown(q)
    assert "B7" in md and "actes CCAM" in md
    assert len(q.questions()) > 40


def test_apply_answers_example():
    r = apply_answers_file(EXAMPLES / "questionnaire" / "reponses_exemple.yaml")
    assert not r.errors, r.errors
    h = load_hospital(r.config)
    assert h.resources["salle_bloc"].count == 9
    assert h.resources["salle_bloc"].shift.start == "07:45"
    assert h.resources["chirurgien"].shift.end == "19:00"
    assert h.name.startswith("Centre hospitalier du Val")
    assert "H1" in r.context_notes


def test_missing_required_reported():
    r = apply_answers({})
    assert any(m.startswith("B1") for m in r.missing_required)
