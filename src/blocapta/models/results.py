"""Résultats structurés de simulation : seules sources de vérité pour le rapport."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FrictionType = Literal[
    "cardinalite",  # le logiciel impose moins d'éléments par saisie que la réalité
    "couverture",  # rôle ou tâche non pris en charge
    "interoperabilite",  # flux manquant → double saisie
    "ressource",  # attente d'un poste informatique
    "disponibilite",  # logiciel indisponible à l'heure de la tâche
    "charge",  # dépassement du nombre d'utilisateurs simultanés
    "panne",  # logiciel en panne : mode dégradé puis resaisie
    "adoption",  # l'agent contourne l'outil faute de confiance
]
Severity = Literal["critique", "majeure", "mineure", "info"]


class FrictionEvent(BaseModel):
    type: FrictionType
    pathway: str
    step: str
    role: str
    task_kind: str
    time_lost_min: float = 0.0
    items_at_risk: int = 0
    t: float = 0.0
    detail: str = ""


class FrictionSummary(BaseModel):
    type: FrictionType
    pathway: str
    step: str
    role: str
    task_kind: str
    occurrences_per_replication: float
    affected_share: float = Field(description="Part des tâches concernées (0-1)")
    time_lost_hours_per_replication: float
    items_at_risk_per_replication: float
    occurrences_per_day: float = 0.0
    time_lost_hours_per_day: float = 0.0
    severity: Severity
    example: str


class Stat(BaseModel):
    mean: float
    ci_low: float
    ci_high: float
    n: int


class KpiComparison(BaseModel):
    kpi: str
    label: str
    unit: str
    baseline: Stat
    software: Stat
    delta: float
    delta_pct: float | None


class StaticFinding(BaseModel):
    type: FrictionType
    severity: Severity
    detail: str


class HumanSummary(BaseModel):
    """Résultats du facteur humain (moyennes sur les réplications)."""

    roles: list[str] = Field(default_factory=list)
    trust_by_day: dict[str, list[float]] = Field(default_factory=dict, description="métier -> confiance moyenne par jour")
    special_agents: dict[str, list[float]] = Field(default_factory=dict, description="sceptiques / champions : confiance par jour")
    usage_rate_by_role: dict[str, float] = Field(default_factory=dict, description="% d'usages réels de l'outil")
    final_trust_by_role: dict[str, float] = Field(default_factory=dict)
    sw_minutes_by_week: list[float] = Field(default_factory=list, description="temps moyen d'une saisie outil par semaine")
    outages: float = 0.0
    outage_minutes: float = 0.0
    parameters: dict[str, float | str] = Field(default_factory=dict)


class SimulationReport(BaseModel):
    hospital_id: str
    software_name: str | None
    days: int
    replications: int
    seed: int
    kpis: list[KpiComparison] = Field(default_factory=list)
    frictions: list[FrictionSummary] = Field(default_factory=list)
    static_findings: list[StaticFinding] = Field(default_factory=list)
    unused_touchpoints: list[str] = Field(default_factory=list)
    scenario: str | None = None
    human: HumanSummary | None = None
