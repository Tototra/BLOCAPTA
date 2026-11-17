"""Validation d'une fiche logiciel : agent 1 (complétude) + grille réglementaire Go/NoGo."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..llm import LLMClient
from ..models.fiche import FicheLogiciel
from .completeness import CompletudeResultat, check_completeness
from .extractor import extract_fiche, read_document
from .rules import CriteriaSet, CriterionResult, evaluate, load_criteria

_WEIGHTS = {"bloquant": 5, "majeur": 3, "mineur": 1}


class FicheValidation(BaseModel):
    fiche: FicheLogiciel
    completude: CompletudeResultat
    reglementaire: list[CriterionResult]
    go_nogo: Literal["GO", "NO_GO"] = Field(description="NO_GO si un critère obligatoire réglementaire échoue")
    score_reglementaire: float = Field(description="Conformité réglementaire pondérée, 0-100")

    @property
    def admissible(self) -> bool:
        """La simulation ne démarre que si l'agent 1 juge la fiche analysable."""
        return self.completude.verdict != "NON_ANALYSABLE"

    @property
    def blocking_failures(self) -> list[CriterionResult]:
        return [r for r in self.reglementaire if r.status == "echec" and r.severity == "bloquant"]


def validate_fiche(
    fiche: FicheLogiciel, criteria: CriteriaSet | None = None, llm: LLMClient | None = None
) -> FicheValidation:
    criteria = criteria or load_criteria()
    reg = evaluate(fiche.model_dump(), criteria)
    applicable = [r for r in reg if r.status != "non_applicable"]
    total = sum(_WEIGHTS[r.severity] for r in applicable) or 1
    ok = sum(_WEIGHTS[r.severity] for r in applicable if r.status == "ok")
    return FicheValidation(
        fiche=fiche,
        completude=check_completeness(fiche, llm=llm),
        reglementaire=reg,
        go_nogo="NO_GO" if any(r.status == "echec" and r.severity == "bloquant" for r in reg) else "GO",
        score_reglementaire=round(100 * ok / total, 1),
    )


def validate_document(
    path: Path, llm: LLMClient | None, known_task_kinds: set[str] | None = None, criteria: CriteriaSet | None = None
) -> FicheValidation:
    doc = read_document(path)
    if isinstance(doc, FicheLogiciel):
        return validate_fiche(doc, criteria=criteria, llm=llm)
    if llm is None:
        raise RuntimeError(
            "Ce document n'est pas structuré (YAML/JSON) : un LLM est nécessaire pour l'extraire. "
            "Activez BLOCAPTA_LLM_ENABLED et lancez Ollama, ou remplissez le template structuré."
        )
    return validate_fiche(extract_fiche(doc, llm, known_task_kinds), criteria=criteria, llm=llm)
