"""Faits structurés de l'audit : seul matériau autorisé pour le LLM de rédaction."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..models.hospital import Hospital
from ..models.results import SimulationReport
from ..spec.completeness import Hypothese
from ..spec.validator import FicheValidation
from .scoring import CompatibilityScore

# KPI mis en avant dans le rapport (les autres restent en annexe)
HEADLINE_KPIS = [
    "temps_documentation_h",
    "temps_documentation_moy_min",
    "saisies_total",
    "elements_a_risque",
    "duree_parcours_moy_min",
    "attente_ressources_moy_min",
    "occupation_salles_pct",
    "taux_debordement_pct",
    "cas_deprogrammes",
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
    hypotheses: list[str] = Field(default_factory=list)
    to_calibrate: list[str] = Field(default_factory=list)
    human: dict | None = None


def build_facts(
    hospital: Hospital,
    validation: FicheValidation,
    score: CompatibilityScore,
    sim: SimulationReport | None,
    hypotheses: list[Hypothese] | None = None,
) -> AuditFacts:
    fiche = validation.fiche
    comp = validation.completude
    headline = []
    if sim:
        by_key = {k.kpi: k for k in sim.kpis}
        keys = list(HEADLINE_KPIS)
        if hospital.programme is None:
            keys.insert(5, "depassement_horaire_min_jour")
        for key in keys:
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
        # temps de documentation regroupé par métier (chirurgiens de toutes spécialités, etc.)
        fam: dict[str, list[float]] = {}
        for k in sim.kpis:
            if k.kpi.startswith("temps_documentation_h."):
                pool = k.kpi.split(".", 1)[1]
                res = hospital.resources.get(pool)
                name = (res.role if res and res.role else pool)
                acc = fam.setdefault(name, [0.0, 0.0])
                acc[0] += k.baseline.mean
                acc[1] += k.software.mean
        for name, (b, sw_) in sorted(fam.items()):
            headline.append(
                {
                    "kpi": f"temps_documentation_h.{name}",
                    "label": f"Temps de documentation – {name}",
                    "unit": "h",
                    "baseline": round(b, 4),
                    "software": round(sw_, 4),
                    "delta": round(sw_ - b, 4),
                    "delta_pct": round(100 * (sw_ - b) / b, 2) if b else None,
                }
            )
    to_calibrate = [x for x in str(hospital.metadata.get("parametres_a_calibrer") or "").split(" | ") if x]
    human = None
    if sim and sim.human:
        hs = sim.human
        to_calibrate += [k for k in hs.parameters if "calibrer" in k]
        human = {
            "scenario": sim.scenario,
            "final_trust_by_role": {r: v[-1] for r, v in hs.trust_by_family.items() if v} or hs.final_trust_by_role,
            "usage_rate_by_role": hs.usage_by_family or hs.usage_rate_by_role,
            "weekly_trust_by_role": {r: v[::7] for r, v in (hs.trust_by_family or hs.trust_by_day).items()},
            "special_agents": {k: {"debut": v[0], "fin": v[-1]} for k, v in hs.special_agents.items() if v},
            "sw_minutes_by_week": hs.sw_minutes_by_week,
            "outages": hs.outages,
            "outage_minutes": hs.outage_minutes,
            "parameters": hs.parameters,
        }
    reg_fail = [r for r in validation.reglementaire if r.status == "echec"]
    return AuditFacts(
        hospital={
            "id": hospital.id,
            "name": hospital.name,
            "archetype": hospital.archetype,
            "services": [s.label for s in hospital.services.values()],
            "pathways": len(hospital.pathways),
        },
        software={
            "name": fiche.identite.nom_version,
            "vendor": fiche.identite.editeur,
            "type": fiche.identite.type_outil,
            "status": fiche.identite.statut_projet,
            "problem": fiche.contexte.probleme,
        },
        validation={
            "admissible": validation.admissible,
            "verdict": comp.verdict,
            "confidence": comp.confiance,
            "completeness": comp.score_completude,
            "incomplete_fields": [
                {"id": c.id, "champ": c.champ, "requis": c.statut_requis, "statut": c.statut_champ, "raison": c.raison}
                for c in comp.champs
                if c.statut_requis != "F"
            ],
            "alerts": [{"type": a.type, "champ": a.champ_id, "detail": a.detail} for a in comp.alertes],
            "questions": [q.question for q in comp.questions_a_l_auteur],
            "summary": comp.resume,
            "go_nogo": validation.go_nogo,
            "regulatory_score": validation.score_reglementaire,
            "failed": [{"id": r.id, "label": r.label, "severity": r.severity} for r in reg_fail],
        },
        score=score,
        simulation=sim,
        headline_kpis=headline,
        hypotheses=[h.hypothese for h in (hypotheses or [])],
        to_calibrate=to_calibrate,
        human=human,
    )
