# ruff: noqa: B023  (la fonction steps() est appelée dans la même itération de boucle)
"""Construction du bloc opératoire de référence à partir des données réelles agrégées.

Entrées :
- ``data/reference/oproom_stats.json`` : statistiques anonymes de l'export OPROOM ;
- ``data/reference/effectifs_bloc.yaml`` : effectifs, horaires, équipements, hypothèses.

Sortie : une configuration ``Hospital`` (dict) prête pour la simulation, dont chaque
valeur non mesurée est listée dans ``metadata.parametres_a_calibrer``.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

from .settings import DATA_DIR

REFERENCE_DIR = DATA_DIR / "reference"
MIN_CASES = 10  # spécialités trop rares ignorées (PMO, actes d'anesthésie seuls)


def load_stats(path: Path | None = None) -> dict:
    return json.loads((path or REFERENCE_DIR / "oproom_stats.json").read_text(encoding="utf-8"))


def load_staffing(path: Path | None = None) -> dict:
    return yaml.safe_load((path or REFERENCE_DIR / "effectifs_bloc.yaml").read_text(encoding="utf-8"))


def lognormal_from_log(mu: float, sigma: float) -> dict:
    mean = math.exp(mu + sigma**2 / 2)
    sd = mean * math.sqrt(math.exp(sigma**2) - 1)
    return {"dist": "lognormal", "mean": round(mean, 2), "sd": round(max(sd, 0.1), 2)}


def lognormal_from_quantiles(median: float, p90: float) -> dict:
    """Log-normale qui respecte la médiane et le 90e centile observés (z(0,9) = 1,2816)."""
    sigma = max(0.05, (math.log(p90) - math.log(median)) / 1.2816)
    return lognormal_from_log(math.log(median), sigma)


def _slug(name: str) -> str:
    table = str.maketrans("éèêàâîôûç", "eeeaaiouc")
    return "".join(c if c.isalnum() else "_" for c in name.lower().translate(table)).strip("_")


def _tri(d: dict) -> dict:
    return {"dist": "triangular", "low": d["low"], "mode": d["mode"], "high": d["high"]}


def _ln(d: dict) -> dict:
    return {"dist": "lognormal", "mean": d["mean"], "sd": d["sd"]}


def build_reference_bloc(stats: dict | None = None, staffing: dict | None = None) -> dict:
    stats = stats or load_stats()
    st = staffing or load_staffing()
    infra, ass, doc = st["infrastructure"], st["assumed_durations"], st["documentation"]
    weekdays, all_days = [0, 1, 2, 3, 4], list(range(7))
    to_calibrate: list[str] = []

    # ------------------------------------------------------------ ressources
    resources: dict[str, dict] = {}
    for name, s in st["staff"].items():
        resources[name] = {"label": s["label"], "role": s["role"], "shifts": s["shifts"], "service": "bloc"}
        if s.get("calibration"):
            resources[name]["calibration"] = s["calibration"]
            to_calibrate.append(f"Effectifs par plage horaire : {s['label']}")
    # supervision : un MAR prend en charge au plus 2 patients simultanément (SFAR / CNP ARMPO 2024)
    resources["mar_supervision"] = {
        "label": "Places de supervision anesthésique (2 patients par MAR)",
        "role": "mar",
        "service": "bloc",
        "shifts": [
            {**sh, "count": sh["count"] * 2, **({"per_unit": sh["per_unit"] * 2, "extra": sh.get("extra", 0) * 2} if sh.get("follows") else {})}
            for sh in st["staff"]["mar"]["shifts"]
        ],
    }
    # SSPI : capacité limitée par les lits ET par le personnel présent
    ratio = infra["sspi_patients_per_nurse"]
    resources["ide_sspi_place"] = {
        "label": f"Places surveillables en SSPI ({ratio} patients par IDE)",
        "kind": "salle",
        "service": "bloc",
        "shifts": [{**sh, "count": sh["count"] * ratio} for sh in st["staff"]["ide_sspi"]["shifts"]],
        "calibration": "à calibrer",
    }
    to_calibrate.append(f"Patients surveillés par IDE de SSPI : {ratio}")
    for name, s in st["surgeons"].items():
        resources[name] = {
            "label": s["label"],
            "role": "chirurgien",
            "service": "bloc",
            "shifts": [
                {"start": "08:00", "end": "18:30", "count": s["team"], "weekdays": weekdays},
                {"start": "18:30", "end": "08:00", "count": 1, "weekdays": all_days},
                {"start": "08:00", "end": "18:30", "count": 1, "weekdays": [5, 6]},
            ],
        }
        if s.get("calibration"):
            to_calibrate.append(f"Effectif : {s['label']}")

    wk = stats["weekday_mean_cases"]
    wk_mean = sum(wk[:5]) / 5
    weekday_factors = [round(v / wk_mean, 4) for v in wk[:5]] + [0.0, 0.0]
    room_rates = [r["open_rate_weekday"] for k, r in stats["rooms"].items() if k.startswith("OP")]
    open_rate = round(sum(room_rates) / len(room_rates), 4)
    rh = infra["room_hours"]
    resources["salle_op"] = {
        "label": f"Salles d'opération (OP 2 à OP 11), ouvertes en moyenne {open_rate:.0%} des jours ouvrés",
        "kind": "salle",
        "service": "bloc",
        "calibration": "mesuré (OPROOM)",
        "shifts": [
            # ouverture corrélée au volume du jour (le programme suit les salles ouvertes)
            *[
                {
                    "start": rh["start"], "end": rh["end"], "count": infra["rooms"], "weekdays": [wd],
                    "availability": round(min(1.0, open_rate * weekday_factors[wd]), 4),
                }
                for wd in weekdays
            ],
            {"start": rh["end"], "end": rh["start"], "count": infra["night_rooms"], "weekdays": all_days, "availability": 1.0},
            {"start": rh["start"], "end": rh["end"], "count": infra["night_rooms"], "weekdays": [5, 6], "availability": 1.0},
        ],
    }
    resources["lit_sspi"] = {"label": "Lits de SSPI", "kind": "salle", "service": "bloc", "count": infra["sspi_beds"]}
    resources["poste_preanesthesie"] = {
        "label": "Postes de pré-anesthésie (assis et couchés)",
        "kind": "salle",
        "service": "bloc",
        "count": infra["preanesthesia_posts"],
        "calibration": "à calibrer",
    }
    to_calibrate.append(f"Postes de pré-anesthésie : {infra['preanesthesia_posts']}")
    to_calibrate.append(f"Début des vacations programmées (ouverture et vérification de salle) : {infra['programme_start']}")
    to_calibrate.append(f"Taux de remplissage du programme opératoire : {infra['programme_fill_ratio']}")
    to_calibrate.append(f"Délai d'appel du patient avant l'heure prévue : {infra['call_ahead_min']} min")
    resources["poste_salle"] = {
        "label": "Postes informatiques fixes en salle",
        "kind": "poste",
        "service": "bloc",
        "count": infra["rooms"] * infra["workstations_per_room"],
    }
    for name, e in st["equipment"].items():
        resources[name] = {"label": e["label"], "kind": "equipement", "service": "bloc", "count": e["count"]}

    # ---------------------------------------------------------------- parcours
    n_days = stats["period"]["days"]
    urg_profile = stats["urgent"]["hourly_profile"]
    shares = ass["phase_shares"]
    sspi_by = ass["sspi_by_anesthesia_min"]
    pathways = []
    room_time_weights: dict[str, float] = {}
    for spe, sp in stats["specialties"].items():
        if sp["n"] < MIN_CASES or spe not in st["specialties"]:
            continue
        cfg = st["specialties"][spe]
        surgeon = cfg["surgeon"]
        slug = _slug(spe)
        if "quantiles_min" in sp:
            q = {float(k): v for k, v in sp["quantiles_min"].items()}
            q[1.0] = min(q[1.0], q[0.99] * 1.2)  # borne haute : on écrête les durées extrêmes au-delà du p99
            case_duration = {"dist": "quantiles", "points": q}
        else:
            case_duration = lognormal_from_quantiles(sp["median_min"], sp["p90_min"])
        mix = sp["anesthesia_mix"]
        sspi_mean = sum(sspi_by.get(k, sspi_by["inconnu"]) * v for k, v in mix.items())
        sspi_mean *= 1 - sp["ambulatory_share"] * (1 - ass["ambulatory_sspi_factor"])
        alr_share = mix.get("ALR", 0.0)
        debout = st["assumed_durations"]["patient_debout_share"].get(spe, 0.0)
        p_brancard = round(1 - debout, 3)

        def steps(urgent: bool) -> list[dict]:
            optional_eq = dict(cfg["equipment"])
            if alr_share:
                optional_eq["echographe"] = round(alr_share, 3)
            pre = [] if urgent else [
                {
                    "id": "accueil_preanesthesie",
                    "label": "Accueil, vérifications et préparation en pré-anesthésie",
                    "duration_min": _ln(ass["accueil_preanesthesie_min"]),
                    "resources": {"poste_preanesthesie": 1},
                    "carry": ["poste_preanesthesie"],
                }
            ]
            return [
                {
                    "id": "brancardage_aller",
                    "label": "Service → bloc (brancard, fauteuil ou à pied)",
                    "duration_min": _ln(ass["brancardage_min"]),
                    "optional_resources": {"brancardier_service": p_brancard},
                },
                *pre,
                {
                    "id": "installation",
                    "label": "Entrée en salle et installation sur la table",
                    "duration_share": shares["installation"],
                    "resources": {"salle_op": 1, "iade": 1, "brancardier_bloc": 1},
                    "carry": ["salle_op", "iade"],
                },
                {
                    "id": "induction",
                    "label": "Induction anesthésique (MAR présent, une induction à la fois)",
                    "duration_share": shares["induction"],
                    "resources": {"salle_op": 1, "iade": 1, "mar": 1},
                    "carry": ["salle_op", "iade"],
                },
                {
                    "id": "intervention",
                    "label": "Incision → fermeture",
                    "duration_share": shares["intervention"],
                    "resources": {"salle_op": 1, "iade": 1, surgeon: 1, "ibode": 1, "mar_supervision": 1},
                    "optional_resources": {**optional_eq, "ide_bloc": 0.5},
                    "carry": ["salle_op", "iade"],
                    "documentation": [
                        {
                            "kind": "tracabilite_actes",
                            "role": surgeon,
                            "current_system": "logiciel_bloc",
                            "items": {"dist": "empirical", "values": doc["ccam_acts_per_case"]},
                            "time_per_entry_min": _tri(doc["time_per_entry_min"]),
                            "time_per_item_min": _tri(doc["time_per_item_min"]),
                            "workstation": "poste_salle",
                        },
                        {
                            "kind": "tracabilite_dm",
                            "role": "ibode",
                            "current_system": "papier",
                            "items": {"dist": "empirical", "values": cfg["dm_items"]},
                            "time_per_entry_min": _tri(doc["dm_time_per_entry_min"]),
                            "time_per_item_min": _tri(doc["dm_time_per_item_min"]),
                        },
                    ],
                },
                {
                    "id": "reveil_sortie",
                    "label": "Pansement, réveil et sortie de salle",
                    "duration_share": shares["reveil"],
                    "resources": {"salle_op": 1, "iade": 1, "mar": 1},
                    "carry": ["salle_op", "iade"],
                },
                {
                    "id": "bionettoyage",
                    "label": "Bionettoyage de la salle (en parallèle du transfert)",
                    "duration_min": _ln(ass["bionettoyage_min"]),
                    "resources": {"salle_op": 1, "ash": 1},
                    "detached": True,
                },
                {
                    "id": "transfert_sspi",
                    "label": "Transfert en SSPI et transmissions (IADE)",
                    "duration_min": _ln(ass["transfert_sspi_min"]),
                    "resources": {"iade": 1, "brancardier_bloc": 1},
                },
                {
                    "id": "sspi",
                    "label": "Surveillance en SSPI",
                    "duration_min": {"dist": "lognormal", "mean": round(sspi_mean, 1), "sd": round(sspi_mean * 0.4, 1)},
                    "resources": {"lit_sspi": 1, "ide_sspi_place": 1},
                },
                {
                    "id": "brancardage_retour",
                    "label": "Bloc → service",
                    "duration_min": _ln(ass["brancardage_min"]),
                    "optional_resources": {"brancardier_service": 1.0 if sp["ambulatory_share"] < 1 else p_brancard},
                },
            ]

        completed = sp["n"]
        urgent_n = completed * sp["urgent_share"]
        prog_n = completed - urgent_n
        # les annulations sont rapportées au seul programmé (une urgence n'est pas programmée à l'avance)
        cancelled_n = completed / (1 - sp["cancellation_rate"]) * sp["cancellation_rate"]
        canc = round(cancelled_n / (prog_n + cancelled_n), 4) if prog_n > 0 else 0.0
        if prog_n > 0:
            # part des salles-jours : proportionnelle au temps de salle programmé de la spécialité
            room_time_weights[f"prog_{slug}"] = round((prog_n + cancelled_n) * sp["mean_min"], 1)
            pathways.append(
                {
                    "id": f"prog_{slug}",
                    "label": f"{spe} — programmé",
                    "service": "bloc",
                    "specialty": spe,
                    "arrivals": {"mode": "planned", "cancellation_rate": canc},
                    "case_duration_min": case_duration,
                    "room_not_before": infra["programme_start"],
                    "room_last_start": infra["last_programmed_start"],
                    "steps": steps(urgent=False),
                }
            )
        if urgent_n >= 1:
            pathways.append(
                {
                    "id": f"urg_{slug}",
                    "label": f"{spe} — urgences",
                    "service": "bloc",
                    "specialty": spe,
                    "urgent": True,
                    "arrivals": {
                        "per_day": {"dist": "fixed", "value": round(urgent_n / n_days, 4)},
                        "window": {"start": "00:00", "end": "23:59", "weekdays": all_days},
                        "hourly_profile": urg_profile,
                        "weekday_factors": [1.0] * 7,
                    },
                    "case_duration_min": case_duration,
                    "steps": steps(urgent=True),
                }
            )

    to_calibrate += [
        "Découpage de l'occupation de salle en phases (installation, induction, intervention, réveil)",
        "Durées de brancardage, d'accueil en pré-anesthésie, de bionettoyage et de transfert",
        "Durées de SSPI par type d'anesthésie",
        "Probabilités d'usage des équipements partagés par spécialité",
        "Nombre d'actes CCAM et de dispositifs médicaux tracés par intervention",
        "Part de patients venant à pied (debout) par spécialité",
    ]
    return {
        "id": "bloc_reference",
        "name": "Bloc opératoire central de référence (10 salles, données OPROOM 2026)",
        "archetype": "bloc_reference",
        "metadata": {
            "type": "bloc opératoire",
            "source": stats["source"],
            "periode": f"{stats['period']['start']} → {stats['period']['end']}",
            "parametres_a_calibrer": " | ".join(to_calibrate),
        },
        "services": {"bloc": {"label": "Bloc opératoire central", "kind": "bloc", "closing_time": rh["end"]}},
        "resources": resources,
        "pathways": pathways,
        "programme": {
            "room_pool": "salle_op",
            "weekdays": weekdays,
            "start": infra["programme_start"],
            "end": infra["last_programmed_start"],
            "fill_ratio": infra["programme_fill_ratio"],
            "turnover_min": stats["targets"]["turnover_median_min"],
            "call_ahead_min": infra["call_ahead_min"],
            "specialty_weights": room_time_weights,
        },
        "information_system": {
            "sso": True,
            "applications": {
                "logiciel_bloc": {"label": "Logiciel de gestion du bloc", "category": "bloc", "standards": ["HL7v2"]},
                "dpi": {"label": "Dossier patient informatisé", "category": "DPI", "standards": ["HL7v2", "FHIR"]},
                "pmsi": {"label": "PMSI / codage", "category": "PMSI", "standards": ["HL7v2"]},
                "papier": {"label": "Registre papier (traçabilité des DM)", "category": "papier"},
            },
            "interfaces": [
                {"source": "logiciel_bloc", "target": "dpi", "standard": "HL7v2", "message": "actes et horaires"},
                {"source": "dpi", "target": "pmsi", "standard": "HL7v2", "message": "actes codés"},
            ],
        },
    }


def fidelity_targets(stats: dict | None = None) -> dict:
    """Valeurs observées que le bloc simulé SANS outil doit retrouver (± 10 %)."""
    stats = stats or load_stats()
    wk = stats["weekday_mean_cases"]
    first = stats["targets"]["first_case_start_median"]
    h, m = first.split(":")
    return {
        "interventions_par_jour_ouvre": round(sum(wk[:5]) / 5, 2),
        "taux_annulation_pct": round(100 * stats["totals"]["cancellation_rate"], 2),
        "occupation_salles_pct": round(100 * stats["targets"]["room_occupancy_rate"], 1),
        "heure_premier_cas_min": int(h) * 60 + int(m),
        "taux_debordement_pct": round(100 * stats["targets"]["overflow_rate"], 1),
        # médianes évaluées seulement si l'échantillon réel est suffisant (≥ 100 cas)
        "duree_mediane_par_specialite_min": {
            spe: v["median_min"] for spe, v in stats["specialties"].items() if v["n"] >= 100
        },
    }
