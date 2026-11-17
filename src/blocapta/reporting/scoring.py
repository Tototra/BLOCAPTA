"""Score de compatibilité 0-100, entièrement déterministe et explicable."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.results import SimulationReport
from ..spec.validator import FicheValidation

FRICTION_PENALTY = {"critique": 20, "majeure": 8, "mineure": 3, "info": 0}
STATIC_PENALTY = {"critique": 12, "majeure": 5, "mineure": 2, "info": 0}
REG_PENALTY = {"bloquant": 10, "majeur": 4, "mineur": 1}


class ScoreLine(BaseModel):
    reason: str
    points: float


class CompatibilityScore(BaseModel):
    score: float
    level: str
    confidence: str = Field(description="Niveau de confiance de l'analyse (agent 1)")
    lines: list[ScoreLine] = Field(default_factory=list)


def _level(score: float, analysable: bool, go: bool) -> str:
    if not analysable:
        return "fiche non analysable"
    if not go:
        return "non déployable en l'état (exigence réglementaire obligatoire manquante)"
    if score >= 75:
        return "compatible"
    if score >= 50:
        return "compatible sous conditions"
    return "incompatible en l'état"


def compute_score(validation: FicheValidation, sim: SimulationReport | None) -> CompatibilityScore:
    lines: list[ScoreLine] = []
    score = 100.0
    for r in validation.reglementaire:
        if r.status == "echec":
            p = REG_PENALTY[r.severity]
            lines.append(ScoreLine(reason=f"Exigence {r.severity} non démontrée : {r.label} ({r.id})", points=-p))
            score -= p
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
    analysable = validation.admissible
    go = validation.go_nogo == "GO"
    if not analysable:
        lines.append(ScoreLine(reason="Fiche non analysable (agent 1) : aucun résultat chiffré, score plafonné à 30", points=0))
        score = min(score, 30.0)
    elif not go:
        lines.append(ScoreLine(reason="NO_GO réglementaire : score plafonné à 40", points=0))
        score = min(score, 40.0)
    score = round(score, 1)
    return CompatibilityScore(
        score=score, level=_level(score, analysable, go), confidence=validation.completude.confiance, lines=lines
    )
