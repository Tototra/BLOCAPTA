"""Score de compatibilité 0-100, entièrement déterministe et explicable."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.results import SimulationReport
from ..spec.validator import SpecValidation

FRICTION_PENALTY = {"critique": 20, "majeure": 8, "mineure": 3, "info": 0}
STATIC_PENALTY = {"critique": 12, "majeure": 5, "mineure": 2, "info": 0}


class ScoreLine(BaseModel):
    reason: str
    points: float


class CompatibilityScore(BaseModel):
    score: float
    level: str
    lines: list[ScoreLine] = Field(default_factory=list)


def _level(score: float, admissible: bool) -> str:
    if not admissible:
        return "fiche technique non admissible"
    if score >= 75:
        return "compatible"
    if score >= 50:
        return "compatible sous conditions"
    return "incompatible en l'état"


def compute_score(validation: SpecValidation, sim: SimulationReport | None) -> CompatibilityScore:
    lines: list[ScoreLine] = []
    score = 100.0
    spec_pen = round((100 - validation.score) * 0.2, 1)
    if spec_pen:
        lines.append(ScoreLine(reason=f"Complétude de la fiche technique ({validation.score} %)", points=-spec_pen))
        score -= spec_pen
    if sim is not None:
        dynamic_types = {f.type for f in sim.frictions}
        for f in sim.frictions:
            p = FRICTION_PENALTY[f.severity]
            if p:
                lines.append(ScoreLine(reason=f"Friction {f.type} ({f.severity}) — {f.pathway}/{f.step}", points=-p))
                score -= p
        for s in sim.static_findings:
            if s.type in dynamic_types:
                continue  # déjà mesuré dynamiquement
            p = STATIC_PENALTY[s.severity]
            if p:
                lines.append(ScoreLine(reason=f"Constat {s.type} ({s.severity})", points=-p))
                score -= p
    score = max(0.0, min(100.0, score))
    if not validation.admissible:
        lines.append(ScoreLine(reason="Critère bloquant non respecté : score plafonné à 30", points=0))
        score = min(score, 30.0)
    score = round(score, 1)
    return CompatibilityScore(score=score, level=_level(score, validation.admissible), lines=lines)
