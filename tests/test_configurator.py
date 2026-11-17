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


@pytest.mark.parametrize("name", ["ch_general", "chu", "clinique_privee", "bloc_reference"])
def test_all_archetypes_load(name):
    h = load_hospital({"id": "t", "name": "t", "extends": name})
    assert h.pathways


def test_archetype_listing():
    assert {"ch_general", "chu", "clinique_privee", "bloc_reference"} <= set(list_archetypes())


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
    assert "F1" in md and "actes CCAM" in md and "pré-anesthésie" in md
    assert len(q.questions()) > 45


def test_apply_answers_example_on_reference_bloc():
    r = apply_answers_file(EXAMPLES / "questionnaire" / "reponses_exemple.yaml")
    assert not r.errors, r.errors
    h = load_hospital(r.config)
    vacations = [s for s in h.resources["salle_op"].shifts if s.label == "vacation"]
    assert len(vacations) == 5 and all(s.count == 8 and s.end == "18:00" for s in vacations)
    assert all(s.count == 1 for s in h.resources["salle_op"].shifts if s.label == "garde")
    assert h.programme.start == "08:15" and h.programme.turnover_min == 9
    prog = [p for p in h.pathways if not p.urgent]
    urg = [p for p in h.pathways if p.urgent]
    assert all(p.room_last_start == "17:30" for p in prog) and all(p.room_last_start is None for p in urg)
    items = prog[0].steps[[s.id for s in prog[0].steps].index("intervention")].documentation[0].items
    assert items.values[2.0] == pytest.approx(0.36)
    assert h.name.startswith("Centre hospitalier du Val")
    assert "H1" in r.context_notes


def test_wildcard_selectors():
    from blocapta.configurator.patching import expand_pointer

    cfg = load_hospital_dict({"id": "t", "name": "t", "extends": "bloc_reference"})
    assert len(expand_pointer(cfg, "/pathways[*]/steps[id=intervention]")) == len(cfg["pathways"])
    assert len(expand_pointer(cfg, "/resources/salle_op/shifts[*label=garde]")) == 2


def test_missing_required_reported():
    r = apply_answers({})
    assert any(m.startswith("B1") for m in r.missing_required)
    assert any(m.startswith("G8") for m in r.missing_required)
