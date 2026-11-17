"""Modèle déclaratif d'un hôpital (brique B du jumeau numérique).

Un hôpital est décrit par :
- des **pools de ressources** (humaines, salles, postes informatiques) avec leurs horaires ;
- des **parcours** (suite d'étapes) et leurs arrivées ;
- des **tâches de documentation** rattachées aux étapes (là où les logiciels interviennent) ;
- son **système d'information** (applications, interfaces, standards).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .distributions import Distribution

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def hhmm_to_minutes(value: str) -> int:
    h, m = value.split(":")
    return int(h) * 60 + int(m)


class TimeWindow(BaseModel):
    """Plage horaire quotidienne, ex. 07:30 → 19:00. Fin < début = plage de nuit."""

    start: str = "00:00"
    end: str = "23:59"
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], description="0 = lundi")

    @field_validator("start", "end")
    @classmethod
    def _fmt(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError(f"heure invalide '{v}', format attendu HH:MM")
        return v

    @property
    def start_min(self) -> int:
        return hhmm_to_minutes(self.start)

    @property
    def end_min(self) -> int:
        return hhmm_to_minutes(self.end)

    def contains(self, minute_of_week: float) -> bool:
        day = int(minute_of_week // 1440) % 7
        m = minute_of_week % 1440
        if self.start_min <= self.end_min:
            return day in self.weekdays and self.start_min <= m < self.end_min
        # plage de nuit : appartient au jour de début
        if m >= self.start_min:
            return day in self.weekdays
        return ((day - 1) % 7) in self.weekdays and m < self.end_min


ResourceKind = Literal["humain", "salle", "poste", "equipement"]


class ResourcePool(BaseModel):
    label: str | None = None
    kind: ResourceKind = "humain"
    count: int = Field(ge=0)
    service: str | None = None
    shift: TimeWindow | None = Field(default=None, description="Horaires de disponibilité ; None = 24h/24")
    mobile: bool = Field(default=False, description="Pour les postes : poste mobile (tablette, chariot)")


class DocumentationTask(BaseModel):
    """Tâche de traçabilité/documentation réalisée à la fin d'une étape.

    C'est le point d'accroche des logiciels : un logiciel testé peut remplacer le
    système actuel (``current_system``) sur un type de tâche (``kind``).
    """

    kind: str = Field(description="Type de tâche, ex. tracabilite_actes, compte_rendu_operatoire")
    role: str = Field(description="Pool de ressources qui réalise la tâche (ex. chirurgien)")
    current_system: str = Field(description="Application utilisée aujourd'hui (doit exister dans le SI)")
    items: Distribution = Field(description="Nombre d'éléments à documenter (ex. actes CCAM)")
    time_per_entry_min: Distribution = Field(description="Temps fixe par saisie (ouverture dossier, validation)")
    time_per_item_min: Distribution = Field(description="Temps par élément documenté")
    workstation: str | None = Field(default=None, description="Pool de postes utilisé aujourd'hui")


class Step(BaseModel):
    id: str
    label: str | None = None
    duration_min: Distribution
    resources: dict[str, int] = Field(default_factory=dict, description="pool -> quantité requise")
    documentation: list[DocumentationTask] = Field(default_factory=list)


class Arrivals(BaseModel):
    per_day: Distribution
    window: TimeWindow = Field(default_factory=lambda: TimeWindow(start="07:30", end="17:00", weekdays=[0, 1, 2, 3, 4]))
    hourly_profile: list[float] | None = Field(
        default=None, description="24 poids relatifs par heure ; None = répartition uniforme dans la plage"
    )

    @field_validator("hourly_profile")
    @classmethod
    def _profile(cls, v):
        if v is not None and (len(v) != 24 or sum(v) <= 0 or min(v) < 0):
            raise ValueError("hourly_profile doit contenir 24 poids positifs")
        return v


class Pathway(BaseModel):
    id: str
    label: str | None = None
    service: str
    arrivals: Arrivals
    steps: list[Step] = Field(min_length=1)


class Service(BaseModel):
    label: str
    kind: str = Field(default="mco", description="bloc, urgences, hospitalisation, consultation, imagerie…")
    beds: int | None = None
    closing_time: str | None = Field(default=None, description="Heure de fin théorique (calcul du dépassement)")


class Application(BaseModel):
    label: str | None = None
    category: str = Field(description="DPI, PACS, LIS, PMSI, pharmacie, bloc, EAI…")
    vendor: str | None = None
    standards: list[str] = Field(default_factory=list)


class Interface(BaseModel):
    source: str
    target: str
    standard: str
    message: str | None = None


class InformationSystem(BaseModel):
    applications: dict[str, Application] = Field(default_factory=dict)
    interfaces: list[Interface] = Field(default_factory=list)
    sso: bool = False
    identity_provider: str | None = None
    hosting_policy: str | None = Field(default=None, description="on_premise, cloud_hds, mixte")
    network: dict[str, str] = Field(default_factory=dict)


class Hospital(BaseModel):
    """Configuration complète d'un établissement."""

    id: str
    name: str
    archetype: str | None = None
    extends: str | None = Field(default=None, description="Archétype parent dont on hérite")
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    services: dict[str, Service] = Field(default_factory=dict)
    resources: dict[str, ResourcePool] = Field(default_factory=dict)
    pathways: list[Pathway] = Field(default_factory=list)
    information_system: InformationSystem = Field(default_factory=InformationSystem)

    @model_validator(mode="after")
    def _references(self):
        errors: list[str] = []
        apps = self.information_system.applications
        for p in self.pathways:
            if p.service not in self.services:
                errors.append(f"parcours '{p.id}' : service inconnu '{p.service}'")
            for s in p.steps:
                for r, q in s.resources.items():
                    if r not in self.resources:
                        errors.append(f"étape '{p.id}/{s.id}' : ressource inconnue '{r}'")
                    elif q > self.resources[r].count:
                        errors.append(
                            f"étape '{p.id}/{s.id}' : demande {q} '{r}' mais le pool n'en contient que {self.resources[r].count}"
                        )
                for d in s.documentation:
                    if d.role not in self.resources:
                        errors.append(f"documentation '{p.id}/{s.id}' : rôle inconnu '{d.role}'")
                    if d.current_system not in apps:
                        errors.append(f"documentation '{p.id}/{s.id}' : application inconnue '{d.current_system}'")
                    if d.workstation and d.workstation not in self.resources:
                        errors.append(f"documentation '{p.id}/{s.id}' : pool de postes inconnu '{d.workstation}'")
        for itf in self.information_system.interfaces:
            for end in (itf.source, itf.target):
                if end not in apps:
                    errors.append(f"interface {itf.source}->{itf.target} : application inconnue '{end}'")
        if errors:
            raise ValueError("Configuration hôpital incohérente :\n- " + "\n- ".join(errors))
        return self

    def documentation_kinds(self) -> set[str]:
        return {d.kind for p in self.pathways for s in p.steps for d in s.documentation}
