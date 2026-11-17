"""Fiche technique normalisée qu'un éditeur doit fournir (brique A).

Tous les champs sont optionnels : ``None`` signifie « non renseigné dans la fiche ».
C'est ce schéma que le LLM d'extraction remplit, et que le moteur de règles vérifie.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Produit(BaseModel):
    nom: str | None = None
    editeur: str | None = None
    version: str | None = None
    description: str | None = None
    categorie: str | None = Field(default=None, description="ex. tracabilite_bloc, prescription, imagerie")


class Reglementaire(BaseModel):
    hebergement_hds: bool | None = Field(default=None, description="Hébergeur certifié HDS (ou on-premise)")
    conformite_rgpd: bool | None = None
    aipd_realisee: bool | None = Field(default=None, description="Analyse d'impact (AIPD) disponible")
    dispositif_medical: bool | None = None
    marquage_ce: bool | None = None
    classe_dm: str | None = Field(default=None, description="I, IIa, IIb, III")
    ins_compatible: bool | None = Field(default=None, description="Gestion de l'Identité Nationale de Santé")
    pro_sante_connect: bool | None = None
    referencement_segur: bool | None = None


class Connecteur(BaseModel):
    cible: str = Field(description="Catégorie d'application cible : DPI, PACS, PMSI, LIS…")
    standard: str = Field(description="HL7v2, FHIR, DICOM, HPRIM, API propriétaire…")
    sens: Literal["entrant", "sortant", "bidirectionnel"] = "bidirectionnel"
    message: str | None = None


class Interoperabilite(BaseModel):
    standards: list[str] = Field(default_factory=list)
    profils_ihe: list[str] = Field(default_factory=list)
    connecteurs: list[Connecteur] = Field(default_factory=list)


class Technique(BaseModel):
    sso: bool | None = Field(default=None, description="Authentification unique (AD, SAML, OIDC)")
    mode_degrade: bool | None = Field(default=None, description="Fonctionnement en cas de panne réseau/serveur")
    hebergement: Literal["on_premise", "cloud_hds", "saas", "mixte"] | None = None
    utilisateurs_simultanes_max: int | None = None
    temps_reponse_ms: int | None = None
    type_poste: Literal["fixe", "mobile", "les_deux"] | None = None
    disponibilite_horaire: str | None = Field(default=None, description="ex. 24/7 ou 07:00-20:00")
    sla_disponibilite_pct: float | None = None


class PointDeContact(BaseModel):
    """Description métier d'une tâche que le logiciel prend en charge."""

    tache: str = Field(description="Type de tâche, ex. tracabilite_actes")
    remplace_systeme_existant: bool = True
    roles: list[str] = Field(default_factory=list, description="Rôles utilisateurs ciblés")
    elements_max_par_saisie: int | None = Field(default=None, description="Ex. 1 acte par saisie ; None = illimité")
    duree_saisie_sec: float | None = Field(default=None, description="Temps fixe moyen par saisie")
    duree_par_element_sec: float | None = None
    poste_requis: Literal["fixe", "mobile", "les_deux"] | None = None


class Metier(BaseModel):
    roles_cibles: list[str] = Field(default_factory=list)
    points_de_contact: list[PointDeContact] = Field(default_factory=list)


class SpecSheet(BaseModel):
    produit: Produit = Field(default_factory=Produit)
    reglementaire: Reglementaire = Field(default_factory=Reglementaire)
    interoperabilite: Interoperabilite = Field(default_factory=Interoperabilite)
    technique: Technique = Field(default_factory=Technique)
    metier: Metier = Field(default_factory=Metier)
