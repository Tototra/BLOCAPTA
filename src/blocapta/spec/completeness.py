"""Agent 1 — Contrôle de complétude de la fiche logiciel (spécification v0.1 du Drive).

Le « portier » de la chaîne : il juge uniquement la fiche, jamais le logiciel.
Règles appliquées de façon déterministe ; un LLM peut affiner l'analyse (champs flous,
promesses commerciales, données personnelles) mais ne peut jamais rendre « complet »
un champ vide.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from ..llm import LLMClient, LLMError
from ..models.fiche import FicheLogiciel
from ..settings import DATA_DIR

StatutChamp = Literal["Complet", "Partiel", "Vide", "Inconnu", "Incohérent"]
Verdict = Literal["NON_ANALYSABLE", "ANALYSABLE_AVEC_RESERVES", "ANALYSABLE"]
Confiance = Literal["elevee", "moyenne", "faible", "aucune"]
TypeAlerte = Literal["rgpd", "incoherence", "affirmation_non_etayee", "unite_manquante", "source_manquante"]

GRID_FILE = DATA_DIR / "grille_completude.yaml"
STRONG_PROOF = {"mesure_site", "etude_publiee"}
_VAGUE = re.compile(
    r"\b(quelques|plusieurs|rapide(ment)?|variable|selon les cas|à définir|a definir|à préciser|tbd|divers|etc)\b",
    re.IGNORECASE,
)
_PROMO = re.compile(
    r"(révolution|zéro erreur|0 erreur|sans aucun risque|100 ?% fiable|aucune panne|gain de \d+ ?%|jamais en panne)",
    re.IGNORECASE,
)
_PERSONAL = [
    re.compile(r"\b[12]\s?\d{2}\s?(0[1-9]|1[0-2])\s?\d{2}\s?\d{3}\s?\d{3}(\s?\d{2})?\b"),  # NIR
    re.compile(r"\b(né|née|date de naissance|ddn)\b[^.\n]{0,20}\d{1,2}/\d{1,2}/\d{2,4}", re.IGNORECASE),
    re.compile(r"\bIPP\s*:?\s*\d{4,}", re.IGNORECASE),
    re.compile(r"\b(Dr|Pr|M\.|Mme|Mr)\s+[A-Z][a-zé]+", re.UNICODE),
    re.compile(r"\bn°\s*de\s*dossier\s*:?\s*\d+", re.IGNORECASE),
]


class FieldSpec(BaseModel):
    id: str
    bloc: int
    champ: str
    statut: Literal["O", "R", "F"]
    path: str
    critique: bool = False
    check: str | None = None
    question: str = ""
    exemple: str = ""


class ChampResultat(BaseModel):
    id: str
    bloc: int
    champ: str
    statut_requis: Literal["O", "R", "F"]
    statut_champ: StatutChamp
    critique: bool = False
    raison: str = ""


class Alerte(BaseModel):
    type: TypeAlerte
    champ_id: str
    detail: str


class Question(BaseModel):
    priorite: int
    champ_id: str
    question: str
    exemple_reponse: str


class Hypothese(BaseModel):
    champ_id: str
    hypothese: str


class CompletudeResultat(BaseModel):
    """Objet JSON produit par l'agent 1 (format de la spécification)."""

    version_agent: str = "0.1"
    version_template: str = "0.1"
    verdict: Verdict
    confiance: Confiance
    score_completude: dict[str, str]
    champs: list[ChampResultat] = Field(description="Champs non complets uniquement")
    alertes: list[Alerte] = Field(default_factory=list)
    questions_a_l_auteur: list[Question] = Field(default_factory=list)
    hypotheses_necessaires: list[Hypothese] = Field(default_factory=list)
    fiche_normalisee: dict | None = None
    resume: str = ""


def load_grid(path: Path | None = None) -> list[FieldSpec]:
    data = yaml.safe_load((path or GRID_FILE).read_text(encoding="utf-8"))
    return [FieldSpec.model_validate(f) for f in data["fields"]]


# ----------------------------------------------------------------- utilitaires
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"\s+", " ", s)


def _resolve(data: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(part)
    return data


def _is_unknown(v: Any) -> bool:
    return isinstance(v, str) and _norm(v) in {"inconnu", "inconnue", "nc", "n/a", "non connu", "?"}


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _text_status(v: Any) -> tuple[StatutChamp, str]:
    if _empty(v):
        return "Vide", "Rien n'est écrit."
    if isinstance(v, list):
        if all(_is_unknown(x) for x in v):
            return "Inconnu", "L'auteur a écrit « Inconnu »."
        return "Complet", ""
    if _is_unknown(v):
        return "Inconnu", "L'auteur a écrit « Inconnu »."
    if isinstance(v, str) and _VAGUE.search(v) and not re.search(r"\d", v):
        return "Partiel", f"Information floue : « {_VAGUE.search(v).group(0)} » sans précision chiffrée."
    return "Complet", ""


def _filled(v: Any) -> bool:
    return not _empty(v) and not _is_unknown(v)


# ----------------------------------------------------------------- règles spéciales
def _check_acteurs(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    if not f.acteurs:
        return "Vide", "Aucun rôle décrit."
    complete, incomplete_users = 0, []
    for a in f.acteurs:
        if a.utilise_logiciel:
            ok = all(_filled(x) for x in (a.actions, a.moment_parcours, a.frequence))
            if ok:
                complete += 1
            else:
                incomplete_users.append(a.role)
        elif a.utilise_logiciel is False and _filled(a.actions or "non utilisateur"):
            complete += 1
    if incomplete_users:
        return "Partiel", f"Rôle(s) utilisateur(s) sans action, moment ou fréquence : {', '.join(incomplete_users)}."
    if not any(a.utilise_logiciel for a in f.acteurs):
        return "Partiel", "Aucun rôle n'est indiqué comme utilisateur du logiciel."
    return ("Complet", "") if complete else ("Partiel", "Aucun rôle complètement décrit.")


def _check_processus(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    if not f.processus:
        return "Vide", "Aucune étape décrite."
    missing = []
    for e in f.processus:
        lacks = [
            name
            for name, v in (("qui", e.qui), ("action", e.action), ("durée sans", e.duree_sans_min),
                            ("durée avec", e.duree_avec_min), ("source", e.source_duree))
            if not _filled(v)
        ]
        if lacks:
            missing.append(f"« {e.etape} » ({', '.join(lacks)})")
    if missing:
        return "Partiel", "Étape(s) incomplète(s) : " + "; ".join(missing) + "."
    return "Complet", ""


def _check_liens(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    if f.donnees.liens_logiciels or f.donnees.aucun_lien:
        return "Complet", ""
    return "Vide", "Ni liens décrits, ni « aucun lien » écrit explicitement."


def _check_disponibilite(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    if f.fiabilite.disponibilite_pct is None:
        return "Vide", "Aucune disponibilité annoncée."
    if not _filled(f.fiabilite.disponibilite_source):
        return "Partiel", "Disponibilité annoncée sans source."
    return "Complet", ""


def _check_reglementaire(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    r = f.risques.contraintes_reglementaires
    points = {
        "dispositif médical": r.dispositif_medical,
        "RGPD": r.conformite_rgpd,
        "hébergement": r.hebergement,
        "traçabilité des accès": r.tracabilite_acces,
    }
    absent = [k for k, v in points.items() if v is None]
    if len(absent) == len(points):
        return "Vide", "Aucune situation réglementaire renseignée."
    if absent:
        return "Partiel", f"Situation non précisée pour : {', '.join(absent)}."
    return "Complet", ""


def _check_indicateurs(f: FicheLogiciel) -> tuple[StatutChamp, str]:
    if not f.indicateurs:
        return "Vide", "Aucun indicateur."
    if any(_filled(i.valeur_actuelle) and _filled(i.cible) for i in f.indicateurs):
        return "Complet", ""
    return "Partiel", "Indicateur sans valeur actuelle ou sans cible."


_CHECKS = {
    "acteurs": _check_acteurs,
    "processus": _check_processus,
    "liens": _check_liens,
    "disponibilite": _check_disponibilite,
    "reglementaire": _check_reglementaire,
    "indicateurs": _check_indicateurs,
}


# ----------------------------------------------------------------- cohérence
def _walk_strings(obj: Any, path: str = ""):
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_strings(v, f"{path}[{i}]")


def _field_id_for_path(path: str, grid: list[FieldSpec]) -> str:
    base = re.sub(r"\[\d+\]", "", path)
    best = max((g for g in grid if base.startswith(g.path)), key=lambda g: len(g.path), default=None)
    return best.id if best else path


def coherence_alerts(f: FicheLogiciel, grid: list[FieldSpec]) -> tuple[list[Alerte], set[str]]:
    alerts: list[Alerte] = []
    incoherent: set[str] = set()
    roles_b2 = {_norm(a.role) for a in f.acteurs}
    users_b2 = {_norm(a.role) for a in f.acteurs if a.utilise_logiciel}
    roles_b4 = {_norm(e.qui) for e in f.processus if _filled(e.qui)}
    for e in f.processus:
        if _filled(e.qui) and _norm(e.qui) not in roles_b2:
            alerts.append(Alerte(type="incoherence", champ_id="B4.etapes",
                                 detail=f"Le rôle « {e.qui} » de l'étape « {e.etape} » n'apparaît pas dans le bloc 2."))
            incoherent.add("B4.etapes")
        if e.moment and f.perimetre.etapes_parcours and e.moment not in f.perimetre.etapes_parcours:
            alerts.append(Alerte(type="incoherence", champ_id="B4.etapes",
                                 detail=f"L'étape « {e.etape} » ({e.moment}) est hors des étapes du parcours déclarées au bloc 3."))
        if _filled(e.duree_sans_min) and _filled(e.duree_avec_min):
            if not _filled(e.source_duree):
                alerts.append(Alerte(type="source_manquante", champ_id="B4.etapes",
                                     detail=f"Durées de l'étape « {e.etape} » sans source."))
            if e.duree_sans_min > 0 and e.duree_avec_min < 0.5 * e.duree_sans_min and e.niveau_preuve not in STRONG_PROOF:
                gain = round(100 * (1 - e.duree_avec_min / e.duree_sans_min))
                alerts.append(Alerte(
                    type="affirmation_non_etayee", champ_id="B4.etapes",
                    detail=f"L'étape « {e.etape} » annonce un gain de {gain} % sans mesure sur site ni étude publiée.",
                ))
    for user in users_b2 - roles_b4:
        alerts.append(Alerte(type="incoherence", champ_id="B2.acteurs",
                             detail=f"Le rôle utilisateur « {user} » n'apparaît dans aucune étape du bloc 4."))
    if f.fiabilite.disponibilite_pct == 100:
        alerts.append(Alerte(type="incoherence", champ_id="B6.disponibilite",
                             detail="Disponibilité annoncée de 100 % : suspecte, aucune panne n'est envisagée."))
    data = f.model_dump()
    seen_promo: set[str] = set()
    for path, text in _walk_strings(data):
        m = _PROMO.search(text)
        if m and path not in seen_promo:
            seen_promo.add(path)
            alerts.append(Alerte(type="affirmation_non_etayee", champ_id=_field_id_for_path(path, grid),
                                 detail=f"Affirmation commerciale non étayée (« {m.group(0)} »)."))
        for rx in _PERSONAL:
            if rx.search(text):
                alerts.append(Alerte(type="rgpd", champ_id=_field_id_for_path(path, grid),
                                     detail="Donnée personnelle probable détectée (non recopiée)."))
                break
    return alerts, incoherent


# ----------------------------------------------------------------- LLM (optionnel)
class _LLMChamp(BaseModel):
    id: str
    statut: Literal["Complet", "Partiel"]
    raison: str = ""


class _LLMReview(BaseModel):
    champs_flous: list[_LLMChamp] = Field(default_factory=list, description="Champs remplis mais trop flous pour simuler")
    affirmations_non_etayees: list[str] = Field(default_factory=list)
    donnees_personnelles_detectees: bool = False


SYSTEM_REVIEW = """Tu es l'agent 1 (contrôle de complétude) de Blocapta. Tu juges uniquement la fiche, jamais le logiciel.
Ne jamais inventer. Ne jamais recopier une donnée personnelle. Signale :
- les champs remplis mais trop flous pour une simulation (statut Partiel) avec une raison courte ;
- les affirmations commerciales sans source mesurée ;
- la présence de noms de patients ou de soignants, numéros de dossier ou dates de naissance."""


def _llm_review(f: FicheLogiciel, results: dict[str, ChampResultat], llm: LLMClient) -> tuple[list[Alerte], dict[str, str]]:
    complete = [r.id for r in results.values() if r.statut_champ == "Complet"]
    prompt = (
        f"Fiche (JSON) :\n{f.model_dump_json()}\n\nChamps jugés complets par les règles : {complete}.\n"
        "Lesquels sont en réalité trop flous ? Y a-t-il des affirmations non étayées ou des données personnelles ?"
    )
    try:
        review = llm.structured(prompt, _LLMReview, system=SYSTEM_REVIEW)
    except LLMError:
        return [], {}
    alerts = [Alerte(type="affirmation_non_etayee", champ_id="fiche", detail=a[:200]) for a in review.affirmations_non_etayees]
    if review.donnees_personnelles_detectees:
        alerts.append(Alerte(type="rgpd", champ_id="fiche", detail="Donnée personnelle détectée par l'analyse (non recopiée)."))
    downgrades = {c.id: c.raison for c in review.champs_flous if c.statut == "Partiel" and c.id in complete}
    return alerts, downgrades


# ----------------------------------------------------------------- agent
def check_completeness(f: FicheLogiciel, llm: LLMClient | None = None, grid: list[FieldSpec] | None = None) -> CompletudeResultat:
    grid = grid or load_grid()
    data = f.model_dump()
    results: dict[str, ChampResultat] = {}
    for g in grid:
        statut, raison = _CHECKS[g.check](f) if g.check else _text_status(_resolve(data, g.path))
        results[g.id] = ChampResultat(
            id=g.id, bloc=g.bloc, champ=g.champ, statut_requis=g.statut, statut_champ=statut,
            critique=g.critique, raison=raison,
        )
    alerts, incoherent = coherence_alerts(f, grid)
    for fid in incoherent:
        results[fid].statut_champ = "Incohérent"
        results[fid].raison = (results[fid].raison + " Contredit un autre champ de la fiche.").strip()
    if llm is not None:
        more, downgrades = _llm_review(f, results, llm)
        alerts += more
        for fid, raison in downgrades.items():
            results[fid].statut_champ = "Partiel"
            results[fid].raison = raison

    ob = [r for r in results.values() if r.statut_requis == "O"]
    rec = [r for r in results.values() if r.statut_requis == "R"]
    fac = [r for r in results.values() if r.statut_requis == "F"]
    filled = {"Complet", "Partiel"}
    rec_filled = sum(r.statut_champ in filled for r in rec)
    personal = any(a.type == "rgpd" for a in alerts)
    blocking = [r for r in ob if r.statut_champ in {"Vide", "Inconnu", "Incohérent"} or (r.critique and r.statut_champ == "Partiel")]
    proofs = [e.niveau_preuve for e in f.processus]
    vendor_only = not proofs or all(p in (None, "declaration_editeur") for p in proofs)
    strong = any(p in STRONG_PROOF for p in proofs)

    if blocking or personal:
        verdict, confiance = "NON_ANALYSABLE", "aucune"
    elif (
        all(r.statut_champ == "Complet" for r in ob)
        and rec_filled >= 0.75 * len(rec)
        and strong
        and not alerts
    ):
        verdict, confiance = "ANALYSABLE", "elevee"
    else:
        verdict = "ANALYSABLE_AVEC_RESERVES"
        user_estimates = any(p in ("estimation_bloc", "retour_utilisateur", *STRONG_PROOF) for p in proofs)
        confiance = "moyenne" if rec_filled >= len(rec) / 2 and user_estimates and not vendor_only else "faible"

    order = {"O": 0, "R": 1, "F": 2}
    todo = sorted(
        [r for r in results.values() if r.statut_champ != "Complet" and r.statut_requis != "F"],
        key=lambda r: (order[r.statut_requis], not r.critique, r.bloc),
    )
    by_id = {g.id: g for g in grid}
    questions = [
        Question(priorite=i + 1, champ_id=r.id, question=by_id[r.id].question, exemple_reponse=by_id[r.id].exemple)
        for i, r in enumerate(todo[:10])
    ]
    hypotheses = []
    if verdict == "ANALYSABLE_AVEC_RESERVES":
        for r in ob:
            if r.statut_champ == "Partiel":
                hypotheses.append(Hypothese(champ_id=r.id, hypothese=f"Information floue complétée par une valeur prudente : {r.raison}"))
        if vendor_only:
            hypotheses.append(Hypothese(
                champ_id="B4.etapes",
                hypothese="Durées « avec le logiciel » issues de l'éditeur seul : incertitude élargie (de -25 % à +50 %).",
            ))
    normalised = None
    if verdict != "NON_ANALYSABLE":
        normalised = {
            g.id: {"valeur": _resolve(data, g.path), "statut": results[g.id].statut_champ} for g in grid
        }
    res = CompletudeResultat(
        verdict=verdict,
        confiance=confiance,
        score_completude={
            "obligatoires": f"{sum(r.statut_champ == 'Complet' for r in ob)}/{len(ob)}",
            "recommandes": f"{rec_filled}/{len(rec)}",
            "facultatifs": f"{sum(r.statut_champ in filled for r in fac)}/{len(fac)}",
        },
        champs=[r for r in results.values() if r.statut_champ != "Complet"],
        alertes=alerts,
        questions_a_l_auteur=questions,
        hypotheses_necessaires=hypotheses,
        fiche_normalisee=normalised,
    )
    res.resume = summary_text(f, res)
    return res


def summary_text(f: FicheLogiciel, r: CompletudeResultat) -> str:
    """Résumé lisible (10 lignes au plus), sans jargon."""
    verdicts = {
        "NON_ANALYSABLE": "La fiche ne permet pas encore l'analyse.",
        "ANALYSABLE_AVEC_RESERVES": "La fiche permet l'analyse, avec des réserves.",
        "ANALYSABLE": "La fiche permet une analyse fiable.",
    }
    solid: list[str] = []
    blocks_ok = sorted({g for g in range(11)} - {c.bloc for c in r.champs if c.statut_requis == "O"})
    if blocks_ok:
        solid = [f"blocs complets : {', '.join(map(str, blocks_ok[:6]))}"]
    lines = [f"Fiche « {f.nom} » - verdict : {r.verdict} (confiance : {r.confiance}). {verdicts[r.verdict]}"]
    lines.append(f"- Complétude : obligatoires {r.score_completude['obligatoires']}, recommandés {r.score_completude['recommandes']}.")
    if solid:
        lines.append(f"- Solide : {solid[0]}.")
    problems = [c for c in r.champs if c.statut_requis == "O"][:3]
    for c in problems:
        lines.append(f"- À compléter : {c.champ} ({c.statut_champ.lower()}).")
    for q in r.questions_a_l_auteur[:3]:
        lines.append(f"- Question {q.priorite} : {q.question}")
    lines.append(
        "La fiche peut passer à l'analyse." if r.verdict != "NON_ANALYSABLE" else "La fiche doit être complétée avant l'analyse."
    )
    return "\n".join(lines[:10])
