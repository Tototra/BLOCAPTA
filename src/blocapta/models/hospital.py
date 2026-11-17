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


class ShiftCount(BaseModel):
    """Une équipe sur une plage horaire : ``count`` personnes présentes de ``start`` à ``end``."""

    label: str | None = Field(default=None, description="Étiquette (vacation, garde, renfort…)")
    start: str
    end: str
    count: int = Field(ge=0)
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])
    availability: float | None = Field(default=None, ge=0, le=1, description="Remplace daily_availability du pool")
    follows: str | None = Field(
        default=None, description="Effectif lié aux unités ouvertes d'un autre pool (ex. 1 IADE par salle ouverte)"
    )
    per_unit: float = Field(default=1.0, ge=0)
    extra: int = Field(default=0, ge=0)

    @property
    def window(self) -> TimeWindow:
        return TimeWindow(start=self.start, end=self.end, weekdays=self.weekdays)


class ResourcePool(BaseModel):
    label: str | None = None
    kind: ResourceKind = "humain"
    role: str | None = Field(default=None, description="Métier générique (chirurgien, iade…) pour relier au logiciel")
    count: int = Field(default=0, ge=0, description="Capacité maximale simultanée (calculée si `shifts`)")
    service: str | None = None
    shift: TimeWindow | None = Field(default=None, description="Horaires de disponibilité ; None = 24h/24")
    shifts: list[ShiftCount] = Field(
        default_factory=list, description="Plusieurs équipes avec leurs effectifs (remplace `shift`)"
    )
    daily_availability: float | None = Field(
        default=None, ge=0, le=1,
        description="Probabilité qu'une unité soit ouverte un jour donné (ex. ouverture des salles)",
    )
    mobile: bool = Field(default=False, description="Pour les postes : poste mobile (tablette, chariot)")
    calibration: str | None = Field(default=None, description="Origine de la valeur : mesuré, déclaré, à calibrer")

    @model_validator(mode="after")
    def _shift_capacity(self):
        if self.shifts:
            if self.shift is not None:
                raise ValueError("utiliser `shift` OU `shifts`, pas les deux")
            peak = 0
            for t in range(0, 7 * 1440, 15):
                peak = max(peak, sum(s.count for s in self.shifts if s.window.contains(t)))
            if self.count < peak:
                self.count = peak
        return self

    def followers(self) -> dict[int, ShiftCount]:
        return {i: s for i, s in enumerate(self.shifts) if s.follows}

    def shift_groups(self) -> list[tuple[TimeWindow | None, int, float | None]]:
        """Liste (plage, effectif, probabilité d'ouverture) ; plage None = 24h/24."""
        if self.shifts:
            return [
                (s.window, s.count, s.availability if s.availability is not None else self.daily_availability)
                for s in self.shifts
            ]
        return [(self.shift, self.count, self.daily_availability)]

    @property
    def role_name(self) -> str | None:
        return self.role


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
    """Étape d'un parcours.

    - ``duration_min`` : durée propre ; ou ``duration_share`` : part de la durée du cas
      (``Pathway.case_duration_min``, tirée une fois par patient) ;
    - ``carry`` : ressources conservées pour l'étape suivante (ex. la salle jusqu'au bionettoyage) ;
      à l'étape suivante, les ressources reçues et non demandées sont libérées dès que les
      nouvelles sont obtenues (effet « tampon » de la pré-anesthésie) ;
    - ``detached`` : l'étape se déroule en parallèle du reste du parcours (ex. bionettoyage
      pendant le transfert en SSPI) avec les ressources reçues qu'elle demande ;
    - ``optional_resources`` : ressources demandées avec une probabilité (équipements partagés).
    """

    id: str
    label: str | None = None
    duration_min: Distribution | None = None
    duration_share: float | None = Field(default=None, gt=0, le=1)
    resources: dict[str, int] = Field(default_factory=dict, description="pool -> quantité requise")
    optional_resources: dict[str, float] = Field(default_factory=dict, description="pool -> probabilité")
    carry: list[str] = Field(default_factory=list)
    detached: bool = False
    documentation: list[DocumentationTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _duration(self):
        if (self.duration_min is None) == (self.duration_share is None):
            raise ValueError(f"étape '{self.id}' : renseigner duration_min OU duration_share")
        return self


class Arrivals(BaseModel):
    mode: Literal["poisson", "planned"] = Field(
        default="poisson", description="planned : cas générés par le programme opératoire (Hospital.programme)"
    )
    per_day: Distribution | None = None
    window: TimeWindow = Field(default_factory=lambda: TimeWindow(start="07:30", end="17:00", weekdays=[0, 1, 2, 3, 4]))
    hourly_profile: list[float] | None = Field(
        default=None, description="24 poids relatifs par heure ; None = répartition uniforme dans la plage"
    )
    weekday_factors: list[float] | None = Field(
        default=None, description="7 multiplicateurs du volume (lundi → dimanche)"
    )
    cancellation_rate: float = Field(default=0.0, ge=0, lt=1, description="Part des cas annulés avant le bloc")

    @field_validator("weekday_factors")
    @classmethod
    def _factors(cls, v):
        if v is not None and (len(v) != 7 or min(v) < 0):
            raise ValueError("weekday_factors doit contenir 7 valeurs positives")
        return v

    @model_validator(mode="after")
    def _per_day(self):
        if self.mode == "poisson" and self.per_day is None:
            raise ValueError("arrivées poisson : per_day est obligatoire")
        return self

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
    specialty: str | None = None
    urgent: bool = Field(default=False, description="Les urgences passent avant le programmé")
    arrivals: Arrivals
    case_duration_min: Distribution | None = Field(
        default=None, description="Durée d'occupation de salle du cas, répartie entre les étapes via duration_share"
    )
    room_last_start: str | None = Field(
        default=None, description="Heure après laquelle un cas programmé n'est plus démarré (déprogrammé)"
    )
    room_not_before: str | None = Field(
        default=None, description="Heure avant laquelle un cas programmé n'entre pas en salle (ouverture des vacations)"
    )
    steps: list[Step] = Field(min_length=1)

    @model_validator(mode="after")
    def _shares(self):
        if any(s.duration_share for s in self.steps) and self.case_duration_min is None:
            raise ValueError(f"parcours '{self.id}' : duration_share exige case_duration_min")
        return self


class ProgrammeConfig(BaseModel):
    """Programme opératoire : chaque jour, chaque salle ouverte reçoit une spécialité
    et est remplie de cas jusqu'à la fin de vacation."""

    room_pool: str = "salle_op"
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    start: str = "08:30"
    end: str = "18:00"
    fill_ratio: float = Field(default=0.8, gt=0, le=1.2, description="Part de la vacation remplie au programme")
    turnover_min: float = Field(default=7, ge=0, description="Délai prévu entre deux cas (remise en état)")
    call_ahead_min: float = Field(default=60, ge=0, description="Appel du patient avant l'heure prévue")
    specialty_weights: dict[str, float] = Field(
        description="parcours programmé -> part des salles-jours attribuées", min_length=1
    )


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
    programme: ProgrammeConfig | None = None

    @model_validator(mode="after")
    def _references(self):
        errors: list[str] = []
        ids = {p.id for p in self.pathways}
        if self.programme:
            if self.programme.room_pool not in self.resources:
                errors.append(f"programme : pool de salles inconnu '{self.programme.room_pool}'")
            for pid in self.programme.specialty_weights:
                if pid not in ids:
                    errors.append(f"programme : parcours inconnu '{pid}'")
        for name, pool in self.resources.items():
            for sh in pool.shifts:
                if sh.follows and sh.follows not in self.resources:
                    errors.append(f"ressource '{name}' : pool suivi inconnu '{sh.follows}'")
                elif sh.follows and self.resources[sh.follows].shifts and any(
                    x.follows for x in self.resources[sh.follows].shifts
                ):
                    errors.append(f"ressource '{name}' : le pool suivi '{sh.follows}' ne peut pas lui-même en suivre un autre")
        for p in self.pathways:
            if p.arrivals.mode == "planned":
                if not self.programme or p.id not in self.programme.specialty_weights:
                    errors.append(f"parcours '{p.id}' : arrivées 'planned' sans entrée dans programme.specialty_weights")
                if p.case_duration_min is None:
                    errors.append(f"parcours '{p.id}' : arrivées 'planned' exigent case_duration_min")
        apps = self.information_system.applications
        for p in self.pathways:
            if p.service not in self.services:
                errors.append(f"parcours '{p.id}' : service inconnu '{p.service}'")
            for s in p.steps:
                for r in list(s.optional_resources) + s.carry:
                    if r not in self.resources:
                        errors.append(f"étape '{p.id}/{s.id}' : ressource inconnue '{r}'")
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
