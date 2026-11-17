"""Scénarios de déploiement et facteur humain (modèle MOBO).

Sources des mécanismes (note méthodologique MOBO) :
- aversion à la perte : Kahneman et Tversky (1979, 1992), λ ≈ 2,25 ; méta-analyse 2024 ≈ 1,955 ;
- diffusion en réseau : Rogers (1962), Bass (1969), implémentation multi-agents sur réseaux
  signés (Dilucchio et al., 2024) ; gradient d'autorité : Edmondson (2003).
Les coefficients α (apprentissage) et κ (perméabilité sociale) sont à calibrer.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .hospital import _HHMM, hhmm_to_minutes  # noqa: F401  (validation des heures)


class AgentOverride(BaseModel):
    """Profil particulier : un « sceptique » ou un « champion »."""

    pool: str = Field(description="Pool ou métier de l'agent (ex. chir_orthopedie, chirurgien)")
    index: int = Field(default=0, ge=0, description="Numéro de l'agent dans le pool")
    label: str = "agent particulier"
    initial_trust: float | None = Field(default=None, ge=0, le=1)
    authority: float | None = Field(default=None, description="Poids de son influence sur les autres (négatif = antagonisme)")
    alpha: float | None = Field(default=None, gt=0, le=1, description="Vitesse d'apprentissage propre (résistance au changement)")


class HumanFactorConfig(BaseModel):
    enabled: bool = True
    initial_trust: float = Field(default=0.5, ge=0, le=1, description="à calibrer")
    initial_trust_by_role: dict[str, float] = Field(default_factory=dict)
    alpha: float = Field(default=0.10, gt=0, le=1, description="Vitesse d'apprentissage (à calibrer)")
    loss_aversion: float = Field(default=1.955, ge=1, le=3, description="λ : 2,25 (1992) ; 1,955 (méta-analyse 2024)")
    kappa: float = Field(default=0.05, ge=0, le=1, description="Sensibilité aux collègues, par jour (à calibrer)")
    authority_by_role: dict[str, float] = Field(
        default_factory=lambda: {"chirurgien": 3.0, "mar": 2.5, "iade": 1.0, "ibode": 1.0},
        description="Gradient d'autorité (Edmondson) : poids de l'influence d'un métier",
    )
    same_team_factor: float = Field(default=2.0, ge=0, description="Influence renforcée au sein d'une même équipe")
    partial_success_outcome: float = Field(
        default=0.6, ge=0, le=1, description="Résultat perçu d'un usage avec friction (1 = succès, 0 = échec)"
    )
    outage_team_outcome: float = Field(
        default=0.0, ge=0, le=1, description="Résultat perçu d'une panne par toute l'équipe présente (0 = échec)"
    )
    non_user_outage_outcome: float = Field(
        default=0.5, ge=0, le=1, description="Perception d'une panne par un non-utilisateur (0,5 ≈ neutre)"
    )
    support_outage_outcome: float = Field(
        default=0.4, ge=0, le=1, description="Résultat perçu d'une panne prise en charge par le support sur site (à calibrer)"
    )
    team_roles: list[str] = Field(
        default_factory=lambda: ["chirurgien", "mar", "iade", "ibode"],
        description="Métiers inclus dans le réseau d'influence, même s'ils n'utilisent pas l'outil",
    )
    bypass_threshold: float = Field(default=0.3, ge=0, le=1, description="Sous ce seuil, l'agent peut contourner l'outil")
    learning_initial_factor: float = Field(default=1.6, ge=1, description="Temps du 1er usage / temps maîtrisé (à calibrer)")
    learning_half_uses: float = Field(default=15, gt=0, description="Usages pour diviser par 2 le surcoût d'apprentissage")
    overrides: list[AgentOverride] = Field(default_factory=list)


class Incident(BaseModel):
    """Panne programmée du logiciel."""

    day: int = Field(ge=0)
    at: str = "09:00"
    duration_min: float = Field(gt=0)
    label: str = "panne"

    @property
    def start_min(self) -> float:
        return self.day * 1440 + hhmm_to_minutes(self.at)


class Scenario(BaseModel):
    name: str
    description: str = ""
    deployment_day: int = Field(default=0, ge=0, description="0 = lundi de la première semaine")
    deployment_time: str = "08:00"
    random_outages: bool = Field(default=True, description="Pannes aléatoires selon la disponibilité annoncée")
    support_on_site_days: int = Field(default=0, ge=0, description="Jours de présence du support éditeur sur site")
    incidents: list[Incident] = Field(default_factory=list)
    human: HumanFactorConfig = Field(default_factory=HumanFactorConfig)
    volume_factor: float = Field(default=1.0, gt=0, description="Période : 0,55 pour août, 1 sinon")

    @property
    def deployment_min(self) -> float:
        return self.deployment_day * 1440 + hhmm_to_minutes(self.deployment_time)
