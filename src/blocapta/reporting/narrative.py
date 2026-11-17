"""Rédaction du rapport : LLM contraint par les faits, avec repli déterministe."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from ..llm import LLMClient, LLMError
from .factcheck import facts_as_dict, unverified_numbers
from .facts import AuditFacts

log = logging.getLogger(__name__)

SYSTEM = """Tu rédiges le rapport d'audit d'un logiciel pour la DSI d'un hôpital français.
Tu disposes UNIQUEMENT des faits JSON fournis (résultats d'une simulation par jumeau numérique).
Règles impératives :
- N'utilise AUCUN chiffre absent des faits. Tu peux arrondir, convertir des minutes en heures,
  ou une part (0,57) en pourcentage (57 %), rien d'autre.
- Ton factuel, professionnel, sans jargon marketing. Phrases courtes.
- Chaque point de vigilance s'appuie sur une friction ou un critère des faits.
- Les questions à l'éditeur doivent être précises et actionnables.
"""


class VigilancePoint(BaseModel):
    titre: str
    gravite: str = Field(description="critique, majeure, mineure")
    constat: str = Field(description="Ce que la simulation montre, chiffré")
    impact: str = Field(description="Conséquence pour les équipes et l'établissement")
    recommandation: str


class ReportNarrative(BaseModel):
    resume_executif: str = Field(description="5 à 8 phrases pour un directeur")
    points_de_vigilance: list[VigilancePoint] = Field(default_factory=list)
    questions_editeur: list[str] = Field(default_factory=list)
    conditions_deploiement: list[str] = Field(default_factory=list)
    generated_by: str = "deterministe"
    unverified_numbers: list[str] = Field(default_factory=list)


_TYPE_LABELS = {
    "cardinalite": "Nombre d'éléments par saisie insuffisant",
    "couverture": "Rôle ou tâche non couvert",
    "interoperabilite": "Interface manquante : double saisie",
    "ressource": "Accès aux postes informatiques",
    "disponibilite": "Logiciel indisponible au moment de la tâche",
    "charge": "Dépassement du nombre d'utilisateurs simultanés",
}
_RECO = {
    "cardinalite": "Exiger de l'éditeur la saisie de plusieurs éléments par fiche, ou chiffrer le temps perdu avant signature.",
    "couverture": "Faire étendre les droits et écrans aux rôles concernés, ou prévoir l'organisation de retranscription.",
    "interoperabilite": "Conditionner le déploiement au développement du connecteur manquant (via l'EAI).",
    "ressource": "Prévoir des postes supplémentaires ou un accès mobile.",
    "disponibilite": "Négocier une disponibilité couvrant toute la plage d'activité, astreintes comprises.",
    "charge": "Dimensionner la licence au pic d'utilisateurs simultanés mesuré.",
}


def deterministic_narrative(facts: AuditFacts) -> ReportNarrative:
    sw = facts.software.get("name") or "Le logiciel"
    sim = facts.simulation
    s = facts.score
    parts = [f"{sw} obtient un score de compatibilité de {s.score}/100 ({s.level}) pour {facts.hospital['name']}."]
    if not facts.validation["admissible"]:
        bloq = [f["label"] for f in facts.validation["failed"] if f["severity"] == "bloquant"]
        parts.append("La fiche technique ne respecte pas les critères bloquants : " + "; ".join(bloq) + ".")
    points: list[VigilancePoint] = []
    if sim:
        parts.append(f"La simulation couvre {sim.days} jours d'activité et {sim.replications} réplications.")
        for k in facts.headline_kpis:
            if k["kpi"] == "temps_documentation_h" and k["delta_pct"] is not None:
                parts.append(
                    f"Le temps total de documentation passe de {k['baseline']:.1f} h à {k['software']:.1f} h "
                    f"({k['delta_pct']:+.1f} %)."
                )
        for f in sim.frictions:
            if f.severity == "info":
                continue
            points.append(
                VigilancePoint(
                    titre=_TYPE_LABELS[f.type],
                    gravite=f.severity,
                    constat=(
                        f"{f.example}. Concerne {f.affected_share * 100:.1f} % des tâches '{f.task_kind}' "
                        f"({f.occurrences_per_day:.1f} occurrences par jour d'activité)."
                    ),
                    impact=(
                        f"{f.time_lost_hours_per_day:.2f} h perdues par jour d'activité pour le rôle '{f.role}' "
                        f"({f.time_lost_hours_per_replication:.1f} h sur {sim.days} jours simulés)"
                        + (
                            f", {f.items_at_risk_per_replication:.1f} éléments à risque d'omission."
                            if f.type == "cardinalite" and f.items_at_risk_per_replication
                            else "."
                        )
                    ),
                    recommandation=_RECO[f.type],
                )
            )
    if points:
        parts.append(f"{len(points)} point(s) de vigilance ont été identifiés.")
    conditions = [p.recommandation for p in points if p.gravite in {"critique", "majeure"}]
    return ReportNarrative(
        resume_executif=" ".join(parts),
        points_de_vigilance=points,
        questions_editeur=facts.validation["questions"][:15],
        conditions_deploiement=list(dict.fromkeys(conditions)),
    )


def _narrative_text(n: ReportNarrative) -> str:
    return json.dumps(n.model_dump(exclude={"generated_by", "unverified_numbers"}), ensure_ascii=False)


def generate_narrative(facts: AuditFacts, llm: LLMClient | None, strict: bool = True) -> ReportNarrative:
    fallback = deterministic_narrative(facts)
    if llm is None:
        return fallback
    fdict = facts_as_dict(facts)
    prompt = (
        "Faits de l'audit (JSON) :\n"
        + json.dumps(fdict, ensure_ascii=False)[:50000]
        + "\n\nBrouillon de structure (à reformuler et enrichir sans ajouter de chiffre) :\n"
        + _narrative_text(fallback)
    )
    try:
        out = llm.structured(prompt, ReportNarrative, system=SYSTEM)
    except LLMError as e:
        log.warning("Rédaction LLM impossible, repli déterministe : %s", e)
        return fallback
    bad = unverified_numbers(_narrative_text(out), fdict)
    if bad and strict:
        log.warning("Chiffres non vérifiés dans la rédaction LLM %s : repli déterministe", bad)
        fallback.unverified_numbers = bad
        return fallback
    out.generated_by = f"llm:{llm.model}"
    out.unverified_numbers = bad
    return out
