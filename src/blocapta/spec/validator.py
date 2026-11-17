"""Validation d'une fiche technique : règles déterministes + questions générées."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from ..llm import LLMClient
from ..models.spec_sheet import SpecSheet
from .extractor import Ambiguity, extract_spec, find_ambiguities, read_document
from .rules import CriteriaSet, CriterionResult, evaluate, load_criteria

_WEIGHTS = {"bloquant": 5, "majeur": 3, "mineur": 1}


class SpecValidation(BaseModel):
    spec: SpecSheet
    admissible: bool = Field(description="False si au moins un critère bloquant échoue")
    score: float = Field(description="Score de complétude pondéré, 0-100")
    results: list[CriterionResult]
    questions: list[Ambiguity] = Field(default_factory=list)

    @property
    def blocking_failures(self) -> list[CriterionResult]:
        return [r for r in self.results if r.status == "echec" and r.severity == "bloquant"]


def validate_spec(
    spec: SpecSheet,
    criteria: CriteriaSet | None = None,
    llm: LLMClient | None = None,
    source_text: str | None = None,
) -> SpecValidation:
    criteria = criteria or load_criteria()
    results = evaluate(spec.model_dump(), criteria)
    applicable = [r for r in results if r.status != "non_applicable"]
    total = sum(_WEIGHTS[r.severity] for r in applicable) or 1
    ok = sum(_WEIGHTS[r.severity] for r in applicable if r.status == "ok")
    questions = [
        Ambiguity(champ=", ".join(r.failed_paths), question=f"[{r.id}] {r.label} : merci de préciser ce point.")
        for r in results
        if r.status == "echec"
    ]
    if llm is not None and source_text:
        questions += find_ambiguities(source_text, spec, llm)
    return SpecValidation(
        spec=spec,
        admissible=not any(r.status == "echec" and r.severity == "bloquant" for r in results),
        score=round(100 * ok / total, 1),
        results=results,
        questions=questions,
    )


def validate_document(
    path: Path, llm: LLMClient | None, known_task_kinds: set[str] | None = None, criteria: CriteriaSet | None = None
) -> SpecValidation:
    doc = read_document(path)
    if isinstance(doc, SpecSheet):
        return validate_spec(doc, criteria=criteria)
    if llm is None:
        raise RuntimeError(
            "Ce document n'est pas structuré (JSON/YAML) : un LLM est nécessaire pour l'extraction. "
            "Activez BLOCAPTA_LLM_ENABLED et lancez Ollama."
        )
    spec = extract_spec(doc, llm, known_task_kinds)
    return validate_spec(spec, criteria=criteria, llm=llm, source_text=doc)
