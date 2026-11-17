"""Fiche logiciel à analyser — format machine du « Template fiche logiciel v0.1 » (Drive BLOCAPTA).

Onze blocs numérotés de 0 à 10. Règles de remplissage du template :
- des faits, pas des promesses, avec chiffres et unités ;
- une source par affirmation importante ;
- « Inconnu » plutôt que vide (un champ vide est considéré comme oublié) ;
- aucune donnée de patient ni nom de soignant.

Tous les champs sont optionnels dans le schéma : c'est l'agent de contrôle de
complétude (``spec/completeness.py``) qui décide si la fiche est analysable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NiveauPreuve = Literal["mesure_site", "etude_publiee", "retour_utilisateur", "estimation_bloc", "declaration_editeur"]
MomentParcours = Literal["avant", "en_salle", "sspi", "apres", "hors_bloc"]


class Bloc0Identite(BaseModel):
    nom_version: str | None = Field(default=None, description="Nom exact et version ou module")
    editeur: str | None = None
    type_outil: str | None = Field(
        default=None,
        description="Traçabilité, planning du bloc, dossier d'anesthésie, gestion de stock, stérilisation, aide à la décision, autre",
    )
    statut_projet: str | None = Field(default=None, description="À l'étude, en essai, déployé ailleurs, déployé ici")
    classe_reglementaire: str | None = Field(default=None, description="DM classe I, IIa, IIb, III ou « non dispositif médical »")
    auteur_date: str | None = Field(default=None, description="Fonction de l'auteur de la fiche et date")
    sources: list[str] = Field(default_factory=list, description="Notice, démonstration, visite, essai, avis utilisateur")


class Bloc1Contexte(BaseModel):
    probleme: str | None = Field(default=None, description="2 à 5 phrases : difficulté concrète à régler au bloc")
    situation_actuelle: str | None = Field(default=None, description="Comment on fait aujourd'hui, sans le logiciel")
    resultat_attendu: str | None = Field(default=None, description="Changement espéré, de préférence mesurable")
    pourquoi_maintenant: str | None = None


class Acteur(BaseModel):
    role: str = Field(description="Chirurgien, Anesthésiste, IBODE, IADE, brancardier, cadre, pharmacie…")
    utilise_logiciel: bool | None = None
    actions: str | None = None
    moment_parcours: str | None = None
    frequence: str | None = None
    formation: str | None = None


class Bloc3Perimetre(BaseModel):
    fonctions_incluses: list[str] = Field(default_factory=list)
    fonctions_exclues: list[str] = Field(default_factory=list)
    salles_specialites: str | None = None
    etapes_parcours: list[MomentParcours] = Field(default_factory=list)
    volume: str | None = Field(default=None, description="Utilisateurs, interventions concernées par jour")


class EtapeProcessus(BaseModel):
    numero: int | None = None
    etape: str = Field(description="Nom de l'étape qui change")
    qui: str | None = Field(default=None, description="Rôle qui réalise l'étape (doit exister dans le bloc 2)")
    action: str | None = None
    moment: MomentParcours | None = None
    duree_sans_min: float | None = Field(default=None, ge=0, description="Durée sans le logiciel (minutes)")
    duree_avec_min: float | None = Field(default=None, ge=0, description="Durée avec le logiciel (minutes)")
    unite_duree: Literal["par_cas", "par_element"] = Field(
        default="par_cas", description="La durée s'entend par intervention ou par élément (implant, acte…)"
    )
    duree_ouverture_saisie_min: float | None = Field(
        default=None, ge=0, description="Temps fixe par saisie (ouvrir la fiche, valider), si la durée est par élément"
    )
    source_duree: str | None = None
    niveau_preuve: NiveauPreuve | None = None
    tache_bloc: str | None = Field(
        default=None, description="Tâche correspondante dans le jumeau (ex. tracabilite_dm, tracabilite_actes)"
    )
    elements_max_par_saisie: int | None = Field(default=None, ge=1, description="Ex. 1 acte par saisie ; vide = illimité")


class LienLogiciel(BaseModel):
    cible: str = Field(description="DPI, logiciel de bloc, stock, stérilisation, pharmacie, PMSI…")
    standard: str | None = Field(default=None, description="HL7v2, FHIR, DICOM, HPRIM, CDA, fichier, API propriétaire")
    sens: Literal["entrant", "sortant", "bidirectionnel"] = "bidirectionnel"


class Bloc5Donnees(BaseModel):
    donnees_saisies: str | None = Field(default=None, description="Quoi, et comment (clavier, scan, sélection)")
    donnees_produites: str | None = None
    liens_logiciels: list[LienLogiciel] = Field(default_factory=list)
    aucun_lien: bool | None = Field(default=None, description="True si « aucun lien » est écrit explicitement")
    mode_echange: str | None = None
    materiel: str | None = None
    type_poste: Literal["fixe", "mobile", "les_deux"] | None = None
    donnees_patient_nominatives: bool | None = Field(default=None, description="Le logiciel manipule-t-il des dossiers nominatifs ?")


class Bloc6Fiabilite(BaseModel):
    disponibilite_pct: float | None = Field(default=None, gt=0, le=100)
    disponibilite_source: str | None = None
    mode_degrade: str | None = Field(default=None, description="Que fait-on en cas de panne ?")
    pannes_connues: str | None = None
    support: str | None = Field(default=None, description="Délai de réponse, horaires, présence sur site au démarrage")
    support_sur_site_jours: int | None = Field(default=None, ge=0)
    mises_a_jour: str | None = None
    utilisateurs_simultanes_max: int | None = Field(default=None, ge=1)


class Bloc7Deploiement(BaseModel):
    calendrier: str | None = None
    formation_initiale: str | None = Field(default=None, description="Durée, format, qui est formé")
    accompagnement: str | None = None
    double_saisie: str | None = None


class Reglementaire(BaseModel):
    dispositif_medical: bool | None = None
    marquage_ce: bool | None = None
    conformite_rgpd: bool | None = None
    aipd_realisee: bool | None = None
    hebergement: Literal["on_premise", "cloud_hds", "saas", "mixte"] | None = None
    hds_certifie: bool | None = None
    ins_integre: bool | None = Field(default=None, description="Téléservice INSi (identitovigilance)")
    tracabilite_acces: bool | None = Field(default=None, description="Journalisation infalsifiable des accès")
    chiffrement_tls: bool | None = None
    gestion_droits_rbac: bool | None = None
    matrice_flux: bool | None = None
    pca_pra: bool | None = Field(default=None, description="Plan de continuité / reprise (RPO, RTO) défini")
    sso: bool | None = Field(default=None, description="Annuaire de l'hôpital (AD/LDAP/SSO)")
    pro_sante_connect: bool | None = None
    dmp_mssante: bool | None = None
    traite_imagerie: bool | None = None
    dicom: bool | None = None
    pentest_recent: bool | None = None


class Bloc8Risques(BaseModel):
    contraintes_reglementaires: Reglementaire = Field(default_factory=Reglementaire)
    contraintes_texte: str | None = None
    risques_patient: str | None = None
    risques_organisation: str | None = None


class Bloc9Preuves(BaseModel):
    sites_utilisateurs: str | None = None
    etudes: str | None = None
    retours_soignants: str | None = None
    niveau_preuve: NiveauPreuve | None = None


class Indicateur(BaseModel):
    indicateur: str
    valeur_actuelle: str | None = None
    cible: str | None = None


class FicheLogiciel(BaseModel):
    version_template: str = "0.1"
    identite: Bloc0Identite = Field(default_factory=Bloc0Identite)
    contexte: Bloc1Contexte = Field(default_factory=Bloc1Contexte)
    acteurs: list[Acteur] = Field(default_factory=list)
    perimetre: Bloc3Perimetre = Field(default_factory=Bloc3Perimetre)
    processus: list[EtapeProcessus] = Field(default_factory=list)
    donnees: Bloc5Donnees = Field(default_factory=Bloc5Donnees)
    fiabilite: Bloc6Fiabilite = Field(default_factory=Bloc6Fiabilite)
    deploiement: Bloc7Deploiement = Field(default_factory=Bloc7Deploiement)
    risques: Bloc8Risques = Field(default_factory=Bloc8Risques)
    preuves: Bloc9Preuves = Field(default_factory=Bloc9Preuves)
    indicateurs: list[Indicateur] = Field(default_factory=list)

    @property
    def nom(self) -> str:
        return self.identite.nom_version or "logiciel"
