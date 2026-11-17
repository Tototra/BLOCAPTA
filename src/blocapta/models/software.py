"""Modèle d'un logiciel testé dans le jumeau (brique C).

Il est dérivé de la fiche technique (``from_spec_sheet``) mais peut aussi être
écrit ou ajusté à la main en YAML.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .distributions import Distribution, Fixed
from .hospital import TimeWindow
from .spec_sheet import SpecSheet


class TouchPoint(BaseModel):
    task_kind: str
    replaces_current: bool = True
    roles: list[str] = Field(default_factory=list, description="Rôles supportés ; vide = tous")
    max_items_per_entry: int | None = Field(default=None, ge=1)
    time_per_entry_min: Distribution = Field(default_factory=lambda: Fixed(value=1.0))
    time_per_item_min: Distribution = Field(default_factory=lambda: Fixed(value=0.5))
    requires_fixed_workstation: bool = False
    omission_risk_per_extra_entry: float = Field(
        default=0.05, ge=0, le=1, description="Probabilité d'oubli à chaque saisie supplémentaire de contournement"
    )


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

    @classmethod
    def from_spec_sheet(cls, spec: SpecSheet) -> SoftwareModel:
        """Conversion déterministe fiche technique → modèle de simulation."""
        tps = []
        for pc in spec.metier.points_de_contact:
            kwargs: dict = {
                "task_kind": pc.tache,
                "replaces_current": pc.remplace_systeme_existant,
                "roles": pc.roles or spec.metier.roles_cibles,
                "max_items_per_entry": pc.elements_max_par_saisie,
                "requires_fixed_workstation": (pc.poste_requis or spec.technique.type_poste) == "fixe",
            }
            if pc.duree_saisie_sec is not None:
                kwargs["time_per_entry_min"] = Fixed(value=pc.duree_saisie_sec / 60)
            if pc.duree_par_element_sec is not None:
                kwargs["time_per_item_min"] = Fixed(value=pc.duree_par_element_sec / 60)
            tps.append(TouchPoint(**kwargs))
        return cls(
            name=spec.produit.nom or "logiciel_inconnu",
            vendor=spec.produit.editeur,
            version=spec.produit.version,
            touchpoints=tps,
            interfaces=[
                SoftwareInterface(target_category=c.cible, standard=c.standard, direction=c.sens)
                for c in spec.interoperabilite.connecteurs
            ],
            max_concurrent_users=spec.technique.utilisateurs_simultanes_max,
            availability=_parse_availability(spec.technique.disponibilite_horaire),
            sso=spec.technique.sso,
        )


def _parse_availability(text: str | None) -> TimeWindow | None:
    if not text or text.strip() in {"24/7", "24h/24", "24h/7j"}:
        return None
    m = re.search(r"(\d{1,2})[:h](\d{2})?\s*[-–à]\s*(\d{1,2})[:h](\d{2})?", text)
    if not m:
        return None
    h1, m1, h2, m2 = m.group(1), m.group(2) or "00", m.group(3), m.group(4) or "00"
    return TimeWindow(start=f"{int(h1):02d}:{m1}", end=f"{int(h2):02d}:{m2}")
