"""Génération d'un journal d'événements synthétique (bloc opératoire + brancardage).

Sert de démo et de jeu de test tant que les vraies données ne sont pas disponibles.
Le format produit est exactement celui attendu par ``load_event_log``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# (activité suivante, moyenne en minutes, écart-type)
BLOC_TRANSITIONS: list[tuple[str, float, float]] = [
    ("prise_en_charge_brancardier", 12, 8),
    ("depose_bloc", 8, 3),
    ("entree_salle", 20, 12),
    ("debut_intervention", 25, 8),
    ("fin_intervention", 95, 40),
    ("sortie_salle", 10, 4),
    ("arrivee_sspi", 5, 2),
    ("sortie_sspi", 60, 25),
]
FIRST_ACTIVITY = "demande_brancardage"


def _lognormal(rng, mean, sd):
    sigma2 = np.log(1 + (sd / mean) ** 2)
    return float(rng.lognormal(np.log(mean) - sigma2 / 2, np.sqrt(sigma2)))


def generate_bloc_log(
    days: int = 60, cases_per_day: float = 30, seed: int = 7, start: datetime | None = None
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = start or datetime(2026, 1, 5)  # un lundi
    rows = []
    case = 0
    # profil horaire : forte activité le matin
    hours = np.arange(7, 17)
    weights = np.array([10, 12, 11, 9, 7, 6, 8, 7, 5, 3], dtype=float)
    weights /= weights.sum()
    for d in range(days):
        day = start + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for _ in range(rng.poisson(cases_per_day)):
            case += 1
            t = day + timedelta(hours=int(rng.choice(hours, p=weights)), minutes=int(rng.integers(0, 60)))
            cid = f"C{case:06d}"
            brancardier = f"BR{rng.integers(1, 7):02d}"
            rows.append((cid, FIRST_ACTIVITY, t, None, "service_hospitalisation"))
            for act, mean, sd in BLOC_TRANSITIONS:
                t = t + timedelta(seconds=round(_lognormal(rng, mean, sd) * 60))
                res = brancardier if act in {"prise_en_charge_brancardier", "depose_bloc"} else None
                rows.append((cid, act, t, res, "brancardier" if res else None))
    df = pd.DataFrame(rows, columns=["case_id", "activity", "timestamp", "resource", "role"])
    df["pathway"] = "chirurgie_programmee"
    return df
