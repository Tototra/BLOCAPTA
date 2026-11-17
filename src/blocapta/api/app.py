"""API REST BLOCAPTA (FastAPI). Documentation interactive : /docs"""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import yaml
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

from .. import __version__
from ..calibration import ColumnMapping, build_pathway, normalise
from ..configurator import (
    PatchOp,
    apply_answers,
    apply_patch,
    list_archetypes,
    load_hospital,
    load_hospital_dict,
    load_questionnaire,
    propose_patch,
    render_markdown,
)
from ..llm import get_llm
from ..models.software import SoftwareModel
from ..models.spec_sheet import SpecSheet
from ..pipeline import run_audit
from ..settings import get_settings
from ..simulation import simulate_audit
from ..spec import validate_document, validate_spec

app = FastAPI(
    title="BLOCAPTA",
    version=__version__,
    description="Jumeau numérique hospitalier : audit de compatibilité des logiciels avant déploiement.",
)


def _parse_config(text: str) -> dict:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise HTTPException(422, f"YAML/JSON invalide : {e}") from e
    if not isinstance(data, dict):
        raise HTTPException(422, "La configuration doit être un objet")
    return data


def _hospital(data: dict):
    try:
        return load_hospital(data)
    except Exception as e:  # erreurs de validation lisibles pour l'utilisateur
        raise HTTPException(422, str(e)) from e


# ---------------------------------------------------------------- santé
@app.get("/health")
def health() -> dict:
    s = get_settings()
    ollama = "désactivé"
    if s.llm_enabled:
        try:
            tags = httpx.get(f"{s.ollama_url}/api/tags", timeout=3).json()
            models = {m["name"] for m in tags.get("models", [])}
            ollama = {
                "joignable": True,
                "modeles_requis": {
                    m: (m in models or f"{m}:latest" in models)
                    for m in {s.model_extraction, s.model_report, s.model_configurator}
                },
            }
        except Exception:
            ollama = {"joignable": False, "url": s.ollama_url}
    return {"status": "ok", "version": __version__, "ollama": ollama}


# ----------------------------------------------------- référentiels
@app.get("/archetypes")
def archetypes() -> dict[str, str]:
    return list_archetypes()


@app.get("/archetypes/{name}")
def archetype(name: str) -> dict:
    try:
        return load_hospital_dict({"id": name, "name": name, "extends": name})
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/questionnaire")
def questionnaire() -> dict:
    return load_questionnaire().model_dump()


@app.get("/questionnaire.md", response_class=PlainTextResponse)
def questionnaire_md() -> str:
    return render_markdown(load_questionnaire())


class AnswersIn(BaseModel):
    archetype: str = "ch_general"
    id: str | None = None
    answers: dict[str, Any]
    use_llm: bool = False


@app.post("/questionnaire/apply")
def questionnaire_apply(body: AnswersIn) -> dict:
    llm = get_llm("configurator") if body.use_llm else None
    return apply_answers(body.answers, body.archetype, llm=llm, hospital_id=body.id).model_dump()


# ------------------------------------------------------- fiches techniques
@app.post("/specs/validate")
async def specs_validate(file: UploadFile | None = File(None), spec_json: str | None = Form(None)) -> dict:
    """Valide une fiche : fichier (PDF, TXT, JSON, YAML) ou JSON conforme au schéma SpecSheet."""
    if spec_json:
        return validate_spec(SpecSheet.model_validate_json(spec_json)).model_dump()
    if file is None:
        raise HTTPException(422, "Fournir `file` ou `spec_json`")
    suffix = Path(file.filename or "fiche.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
    try:
        return validate_document(Path(tmp.name), get_llm("extraction")).model_dump()
    except RuntimeError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        Path(tmp.name).unlink(missing_ok=True)


@app.get("/specs/schema")
def specs_schema() -> dict:
    return SpecSheet.model_json_schema()


# --------------------------------------------------------- configuration
class ConfigIn(BaseModel):
    config: dict


class PatchIn(BaseModel):
    config: dict
    operations: list[PatchOp]


class InstructionIn(BaseModel):
    config: dict
    instruction: str = Field(examples=["On passe à 10 salles et les brancardiers travaillent de 6h à 21h"])


@app.post("/hospitals/resolve")
def hospitals_resolve(body: ConfigIn) -> dict:
    return _hospital(body.config).model_dump(mode="json", exclude_none=True)


@app.post("/hospitals/patch")
def hospitals_patch(body: PatchIn) -> dict:
    return apply_patch(load_hospital_dict(body.config), body.operations).model_dump()


@app.post("/hospitals/assist")
def hospitals_assist(body: InstructionIn) -> dict:
    llm = get_llm("configurator")
    if llm is None:
        raise HTTPException(503, "LLM désactivé (BLOCAPTA_LLM_ENABLED=false)")
    patch, result = propose_patch(load_hospital_dict(body.config), body.instruction, llm)
    return {"proposal": patch.model_dump(), "result": result.model_dump()}


# ------------------------------------------------------------ calibration
@app.post("/calibration")
async def calibration(
    file: UploadFile = File(...),
    pathway_id: str = Form("parcours"),
    service: str = Form("bloc"),
    mapping_json: str = Form("{}"),
) -> dict:
    raw_bytes = await file.read()
    if (file.filename or "").lower().endswith((".xlsx", ".xls")):
        raw = pd.read_excel(io.BytesIO(raw_bytes))
    else:
        raw = pd.read_csv(io.BytesIO(raw_bytes), sep=None, engine="python")
    try:
        df = normalise(raw, ColumnMapping.model_validate(json.loads(mapping_json)))
        pw, report = build_pathway(df, pathway_id, service)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {"pathway": pw.model_dump(mode="json"), "report": report.model_dump()}


# ------------------------------------------------------------- simulation
class SimulationIn(BaseModel):
    hospital: dict
    software: SoftwareModel | None = None
    spec: SpecSheet | None = None
    days: int = Field(20, ge=1, le=365)
    replications: int = Field(20, ge=1, le=500)
    seed: int = 42


@app.post("/simulations")
def simulations(body: SimulationIn) -> dict:
    h = _hospital(body.hospital)
    sw = body.software or (SoftwareModel.from_spec_sheet(body.spec) if body.spec else None)
    if sw is None:
        raise HTTPException(422, "Fournir `software` ou `spec`")
    return simulate_audit(h, sw, body.days, body.replications, body.seed).model_dump()


class FidelityIn(BaseModel):
    hospital: dict | None = None
    days: int = Field(56, ge=7, le=365)
    replications: int = Field(10, ge=1, le=100)
    seed: int = 7


@app.post("/fidelity")
def fidelity(body: FidelityIn) -> dict:
    from ..reference import fidelity_targets
    from ..simulation import check_fidelity

    h = _hospital(body.hospital or {"id": "ref", "name": "ref", "extends": "bloc_reference"})
    return check_fidelity(h, fidelity_targets(), body.days, body.replications, body.seed).model_dump()


# ------------------------------------------------------------------ audit
@app.post("/audits")
async def audits(
    hospital_file: UploadFile = File(..., description="Configuration hôpital YAML/JSON (peut utiliser extends)"),
    spec_file: UploadFile = File(..., description="Fiche technique PDF/TXT/JSON/YAML"),
    days: int = Form(20),
    replications: int = Form(20),
    seed: int = Form(42),
    use_llm_report: bool = Form(True),
) -> dict:
    h = _hospital(_parse_config((await hospital_file.read()).decode("utf-8")))
    suffix = Path(spec_file.filename or "fiche.txt").suffix
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await spec_file.read())
    try:
        r = run_audit(
            h, Path(tmp.name), days=days, replications=replications, seed=seed,
            extraction_llm=get_llm("extraction"),
            report_llm=get_llm("report") if use_llm_report else None,
        )
    except RuntimeError as e:
        raise HTTPException(422, str(e)) from e
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return {
        "score": r.facts.score.model_dump(),
        "facts": r.facts.model_dump(),
        "narrative": r.narrative.model_dump(),
        "markdown": r.markdown,
        "html": r.html,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (
        "<h1>BLOCAPTA</h1><p>Jumeau numérique hospitalier. "
        "Documentation de l'API : <a href='/docs'>/docs</a></p>"
    )
