import json

import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from blocapta.api import app as api
from blocapta.cli import app as cli

from .conftest import EXAMPLES

client = TestClient(api)
runner = CliRunner()


def test_api_archetypes_and_questionnaire():
    assert "ch_general" in client.get("/archetypes").json()
    assert client.get("/questionnaire.md").text.startswith("# Questionnaire")


def test_api_validate_fiche_json(fiche):
    r = client.post("/fiches/validate", data={"fiche_json": fiche.model_dump_json()})
    assert r.status_code == 200
    assert r.json()["completude"]["verdict"] == "ANALYSABLE_AVEC_RESERVES"


def test_api_patch():
    r = client.post(
        "/hospitals/patch",
        json={
            "config": {"id": "t", "name": "t", "extends": "ch_general"},
            "operations": [{"op": "replace", "path": "/resources/salle_bloc/count", "value_json": "9"}],
        },
    )
    assert r.json()["ok"]


def test_api_simulation(fiche):
    r = client.post(
        "/simulations",
        json={"hospital": {"id": "t", "name": "t", "extends": "ch_general"}, "fiche": fiche.model_dump(), "days": 3, "replications": 1},
    )
    assert r.status_code == 200
    assert any(f["type"] == "cardinalite" for f in r.json()["frictions"])


def test_api_audit(monkeypatch):
    monkeypatch.setenv("BLOCAPTA_LLM_ENABLED", "false")
    from blocapta.settings import get_settings

    get_settings.cache_clear()
    try:
        files = {
            "hospital_file": ("h.yaml", (EXAMPLES / "hospitals" / "ch_exemple.yaml").read_bytes()),
            "fiche_file": ("s.yaml", (EXAMPLES / "fiches" / "archivactes.yaml").read_bytes()),
        }
        r = client.post("/audits", files=files, data={"days": 3, "replications": 1})
        assert r.status_code == 200, r.text
        assert r.json()["markdown"].startswith("# Rapport")
    finally:
        get_settings.cache_clear()


def test_api_calibration():
    from blocapta.calibration import generate_bloc_log

    csv = generate_bloc_log(days=20, cases_per_day=10).to_csv(index=False).encode()
    r = client.post("/calibration", files={"file": ("log.csv", csv)}, data={"pathway_id": "p", "service": "bloc"})
    assert r.status_code == 200, r.text
    assert len(r.json()["pathway"]["steps"]) == 8


def test_cli_full_flow(tmp_path):
    res = runner.invoke(cli, ["template", "-o", str(tmp_path / "q.md"), "--answers", str(tmp_path / "a.yaml")])
    assert res.exit_code == 0, res.output
    res = runner.invoke(
        cli, ["apply-answers", str(EXAMPLES / "questionnaire" / "reponses_exemple.yaml"), "-o", str(tmp_path / "h.yaml")]
    )
    assert res.exit_code == 0, res.output
    assert yaml.safe_load((tmp_path / "h.yaml").read_text())["resources"]["salle_bloc"]["count"] == 9
    out = tmp_path / "rapport.md"
    res = runner.invoke(
        cli,
        ["audit", str(tmp_path / "h.yaml"), str(EXAMPLES / "fiches" / "archivactes.yaml"),
         "--days", "3", "--replications", "1", "--no-llm", "-o", str(out)],
    )
    assert res.exit_code == 0, res.output
    assert out.exists() and out.with_suffix(".html").exists()
    assert json.loads(out.with_suffix(".json").read_text())["score"]["score"] >= 0


def test_cli_calibrate(tmp_path):
    log = tmp_path / "log.csv"
    assert runner.invoke(cli, ["generate-log", "-o", str(log), "--days", "30"]).exit_code == 0
    res = runner.invoke(cli, ["calibrate", str(log), "-o", str(tmp_path / "p.yaml")])
    assert res.exit_code == 0, res.output


def test_cli_fiche_and_template(tmp_path):
    out = tmp_path / "agent1.json"
    res = runner.invoke(cli, ["fiche", str(EXAMPLES / "fiches" / "scantrace.yaml"), "--no-llm", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert json.loads(out.read_text())["verdict"] == "ANALYSABLE_AVEC_RESERVES"
    tpl = tmp_path / "fiche.yaml"
    assert runner.invoke(cli, ["fiche-template", "-o", str(tpl)]).exit_code == 0
    res = runner.invoke(cli, ["fiche", str(tpl), "--no-llm"])
    assert "NON_ANALYSABLE" in res.output
