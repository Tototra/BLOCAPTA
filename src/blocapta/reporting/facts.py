"""Faits structurés de l'audit : seul matériau autorisé pour le LLM de rédaction."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.hospital import Hospital
from ..models.results import SimulationReport
from ..spec.validator import SpecValidation
from .scoring import CompatibilityScore

# KPI mis en avant dans le rapport (les autres restent en annexe)
HEADLINE_KPIS = [
    "temps_documentation_h",
    "temps_documentation_moy_min",
    "saisies_total",
    "elements_a_risque",
    "duree_parcours_moy_min",
    "depassement_horaire_min_jour",
    "attente_poste_moy_min",
    "pic_utilisateurs_simultanes",
]


class AuditFacts(BaseModel):
    generated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    hospital: dict
    software: dict
    validation: dict
    score: CompatibilityScore
    simulation: SimulationReport | None = None
    headline_kpis: list[dict] = Field(default_factory=list)


def build_facts(
    hospital: Hospital, validation: SpecValidation, score: CompatibilityScore, sim: SimulationReport | None
) -> AuditFacts:
    spec = validation.spec
    headline = []
    if sim:
        by_key = {k.kpi: k for k in sim.kpis}
        for key in HEADLINE_KPIS + [k.kpi for k in sim.kpis if k.kpi.startswith("temps_documentation_h.")]:
            if key in by_key:
                k = by_key[key]
                headline.append(
                    {
                        "kpi": k.kpi,
                        "label": k.label,
                        "unit": k.unit,
                        "baseline": k.baseline.mean,
                        "software": k.software.mean,
                        "delta": k.delta,
                        "delta_pct": k.delta_pct,
                    }
                )
    return AuditFacts(
        hospital={
            "id": hospital.id,
            "name": hospital.name,
            "archetype": hospital.archetype,
            "services": [s.label for s in hospital.services.values()],
            "pathways": [p.label or p.id for p in hospital.pathways],
        },
        software={
            "name": spec.produit.nom,
            "vendor": spec.produit.editeur,
            "version": spec.produit.version,
            "description": spec.produit.description,
        },
        validation={
            "admissible": validation.admissible,
            "completeness_score": validation.score,
            "failed": [
                {"id": r.id, "label": r.label, "severity": r.severity}
                for r in validation.results
                if r.status == "echec"
            ],
            "questions": [q.question for q in validation.questions],
        },
        score=score,
        simulation=sim,
        headline_kpis=headline,
    )
