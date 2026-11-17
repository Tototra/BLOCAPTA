"""Agent 2 — Normalisation : fiche logiciel → paramètres de simulation.

Transforme le bloc 4 (processus avant / après) en points de contact du jumeau, avec une
incertitude qui dépend du niveau de preuve (règle de la checklist : une durée annoncée
par l'éditeur seul voit son incertitude élargie). Chaque valeur supposée est tracée
dans une liste d'hypothèses reprise dans le rapport.
"""

from __future__ import annotations

import re
import unicodedata

from ..models.distributions import Fixed, Triangular
from ..models.fiche import EtapeProcessus, FicheLogiciel
from ..models.scenario import Scenario
from ..models.software import Reliability, SoftwareInterface, SoftwareModel, TouchPoint
from .completeness import Hypothese

ROLE_MAP = {
    "chirurgien": "chirurgien",
    "chirurgiens": "chirurgien",
    "anesthesiste": "mar",
    "medecin anesthesiste": "mar",
    "mar": "mar",
    "ibode": "ibode",
    "iade": "iade",
    "ide": "ide_bloc",
    "ide panseur": "ide_bloc",
    "brancardier": "brancardier",
    "aide-soignant": "aide_soignant",
    "cadre de sante": "cadre",
    "pharmacien": "pharmacien",
    "secretariat": "secretariat",
}
CATEGORY_MAP = {
    "dpi": "DPI",
    "dossier patient": "DPI",
    "logiciel de bloc": "bloc",
    "bloc": "bloc",
    "pmsi": "PMSI",
    "facturation": "PMSI",
    "stock": "stock",
    "pharmacie": "pharmacie",
    "sterilisation": "sterilisation",
    "pacs": "PACS",
}
SPECIALTY_HINTS = {
    "orthop": ["orthop"],
    "viscer": ["generale et digestive", "visceral"],
    "digestiv": ["generale et digestive"],
    "urolog": ["urolog"],
    "gyn": ["gynecolog"],
    "ophtalm": ["ophtalm"],
    "orl": ["orl"],
    "endoscop": ["endoscop"],
    "stomato": ["stomato"],
    "cardio": ["cardio"],
    "robot": ["robot"],
}
TASK_HINTS = [
    (r"implant|dispositif|\bdm\b|udi|tra[cç]abilit[ée] des d", "tracabilite_dm"),
    (r"acte|ccam|codage|cotation", "tracabilite_actes"),
]
# incertitude (bas, haut) selon le niveau de preuve
UNCERTAINTY = {
    "mesure_site": (0.9, 1.1),
    "etude_publiee": (0.9, 1.15),
    "retour_utilisateur": (0.8, 1.3),
    "estimation_bloc": (0.8, 1.3),
    "declaration_editeur": (0.75, 1.5),
    None: (0.75, 1.5),
}


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()


def map_role(label: str | None) -> str | None:
    if not label:
        return None
    n = _norm(label)
    if n in ROLE_MAP:
        return ROLE_MAP[n]
    for k, v in ROLE_MAP.items():
        if k in n:
            return v
    return n.replace(" ", "_")


def map_category(label: str) -> str:
    n = _norm(label)
    for k, v in CATEGORY_MAP.items():
        if k in n:
            return v
    return label


def guess_task(step: EtapeProcessus, known: set[str] | None) -> str | None:
    if step.tache_bloc:
        return step.tache_bloc
    text = _norm(f"{step.etape} {step.action or ''}")
    for rx, kind in TASK_HINTS:
        if re.search(rx, text) and (known is None or kind in known):
            return kind
    return None


def uncertain(value: float, proof: str | None) -> Triangular | Fixed:
    if value <= 0:
        return Fixed(value=0.0)
    lo, hi = UNCERTAINTY.get(proof, UNCERTAINTY[None])
    return Triangular(low=round(value * lo, 3), mode=round(value, 3), high=round(value * hi, 3))


def scope_specialties(text: str | None, known: set[str] | None) -> list[str]:
    """Spécialités du jumeau couvertes par le périmètre écrit dans la fiche (vide = toutes)."""
    if not text or not known:
        return []
    t = _norm(text)
    if re.search(r"\btout(es)?\b", t) and not re.search(r"sauf|hors", t):
        return []
    hits = set()
    for token, patterns in SPECIALTY_HINTS.items():
        if token in t:
            for spe in known:
                if any(p in _norm(spe) for p in patterns):
                    hits.add(spe)
    return sorted(hits)


def fiche_to_software(
    fiche: FicheLogiciel, known_tasks: set[str] | None = None, known_specialties: set[str] | None = None
) -> tuple[SoftwareModel, list[Hypothese]]:
    hyps: list[Hypothese] = []
    scope = scope_specialties(fiche.perimetre.salles_specialites, known_specialties)
    if scope:
        hyps.append(Hypothese(champ_id="B3.salles_specialites", hypothese=f"Outil simulé uniquement pour : {', '.join(scope)}."))
    tps: list[TouchPoint] = []
    fixed_ws = fiche.donnees.type_poste == "fixe"
    for step in fiche.processus:
        kind = guess_task(step, known_tasks)
        if kind is None:
            hyps.append(Hypothese(champ_id="B4.etapes", hypothese=f"Étape « {step.etape} » non reliée à une tâche du jumeau : non simulée."))
            continue
        if not step.tache_bloc:
            hyps.append(Hypothese(champ_id="B4.etapes", hypothese=f"Étape « {step.etape} » rattachée à la tâche « {kind} » par analogie."))
        if step.duree_avec_min is None:
            hyps.append(Hypothese(champ_id="B4.etapes", hypothese=f"Durée avec logiciel inconnue pour « {step.etape} » : durée actuelle conservée."))
            continue
        role = map_role(step.qui)
        dist = uncertain(step.duree_avec_min, step.niveau_preuve)
        if step.niveau_preuve in (None, "declaration_editeur"):
            hyps.append(Hypothese(
                champ_id="B4.etapes",
                hypothese=f"« {step.etape} » : {step.duree_avec_min} min annoncées par l'éditeur, simulées entre "
                f"{dist.low if hasattr(dist, 'low') else 0} et {dist.high if hasattr(dist, 'high') else 0} min.",
            ))
        if step.unite_duree == "par_element":
            item = dist
            if step.duree_ouverture_saisie_min is not None:
                entry = uncertain(step.duree_ouverture_saisie_min, step.niveau_preuve)
            else:
                entry = Fixed(value=0.3)
                hyps.append(Hypothese(champ_id="B4.etapes", hypothese=f"« {step.etape} » : 0,3 min d'ouverture de saisie supposées."))
        else:
            entry, item = dist, Fixed(value=0.0)
        tps.append(
            TouchPoint(
                task_kind=kind,
                specialties=scope,
                roles=[role] if role else [],
                max_items_per_entry=step.elements_max_par_saisie,
                time_per_entry_min=entry,
                time_per_item_min=item,
                requires_fixed_workstation=fixed_ws,
            )
        )
    interfaces = [
        SoftwareInterface(target_category=map_category(lien.cible), standard=lien.standard or "inconnu", direction=lien.sens)
        for lien in fiche.donnees.liens_logiciels
    ]
    avail = fiche.fiabilite.disponibilite_pct
    if avail is None:
        avail = 99.0
        hyps.append(Hypothese(champ_id="B6.disponibilite", hypothese="Disponibilité inconnue : 99,0 % supposés."))
    elif avail >= 100:
        avail = 99.9
        hyps.append(Hypothese(champ_id="B6.disponibilite", hypothese="Disponibilité de 100 % jugée irréaliste : 99,9 % simulés."))
    sw = SoftwareModel(
        name=fiche.identite.nom_version or "logiciel",
        vendor=fiche.identite.editeur,
        touchpoints=tps,
        interfaces=interfaces,
        max_concurrent_users=fiche.fiabilite.utilisateurs_simultanes_max,
        sso=fiche.risques.contraintes_reglementaires.sso,
        reliability=Reliability(availability_pct=avail),
    )
    return sw, hyps


def default_scenario(fiche: FicheLogiciel) -> Scenario:
    """Scénario par défaut : déploiement un lundi à 8 h avec le support annoncé dans la fiche."""
    return Scenario(
        name="Déploiement selon la fiche (lundi 8 h)",
        description="Pannes aléatoires selon la disponibilité annoncée, support sur site selon le bloc 6.",
        support_on_site_days=fiche.fiabilite.support_sur_site_jours or 0,
    )
