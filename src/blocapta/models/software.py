"""Modèle d'un logiciel testé dans le jumeau (brique C).

Il est dérivé de la fiche logiciel par l'agent de normalisation
(``spec.normalize.fiche_to_software``) mais peut aussi être écrit ou ajusté à la main en YAML.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .distributions import Distribution, Fixed
from .hospital import TimeWindow


class TouchPoint(BaseModel):
    task_kind: str
    specialties: list[str] = Field(default_factory=list, description="Spécialités concernées ; vide = toutes")
    replaces_current: bool = True
    roles: list[str] = Field(default_factory=list, description="Rôles supportés ; vide = tous")
    max_items_per_entry: int | None = Field(default=None, ge=1)
    time_per_entry_min: Distribution = Field(default_factory=lambda: Fixed(value=1.0))
    time_per_item_min: Distribution = Field(default_factory=lambda: Fixed(value=0.5))
    requires_fixed_workstation: bool = False
    omission_risk_per_extra_entry: float = Field(
        default=0.05, ge=0, le=1, description="Probabilité d'oubli à chaque saisie supplémentaire de contournement"
    )


class Reliability(BaseModel):
    availability_pct: float = Field(default=99.5, gt=0, le=100, description="Disponibilité annoncée")
    mean_outage_min: float = Field(default=60, gt=0, description="Durée moyenne d'une panne (à calibrer)")
    degraded_time_factor: float = Field(default=1.3, ge=1, description="Surcoût du mode dégradé (papier)")
    reentry_after_outage: bool = Field(default=True, description="Resaisie dans le logiciel après la panne")
    support_outage_factor: float = Field(default=0.5, gt=0, le=1, description="Durée des pannes avec support sur site")


class SoftwareInterface(BaseModel):
    target_category: str
    standard: str
    direction: str = "bidirectionnel"


class SoftwareModel(BaseModel):
    name: str
    vendor: str | None = None
    version: str | None = None
    touchpoints: list[TouchPoint] = Field(default_factory=list)
    interfaces: list[SoftwareInterface] = Field(default_factory=list)
    max_concurrent_users: int | None = None
    availability: TimeWindow | None = None
    sso: bool | None = None
    reliability: Reliability = Field(default_factory=Reliability)



def _parse_availability(text: str | None) -> TimeWindow | None:
    if not text or text.strip() in {"24/7", "24h/24", "24h/7j"}:
        return None
    m = re.search(r"(\d{1,2})[:h](\d{2})?\s*[-–à]\s*(\d{1,2})[:h](\d{2})?", text)
    if not m:
        return None
    h1, m1, h2, m2 = m.group(1), m.group(2) or "00", m.group(3), m.group(4) or "00"
    return TimeWindow(start=f"{int(h1):02d}:{m1}", end=f"{int(h2):02d}:{m2}")
