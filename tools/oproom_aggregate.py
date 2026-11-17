"""Agrège un export OPROOM en statistiques anonymes pour calibrer le jumeau.

Usage :
    python tools/oproom_aggregate.py chemin/vers/OPROOM.xlsx -o src/blocapta/data/reference/oproom_stats.json

Le fichier brut n'est JAMAIS copié dans le dépôt. Seules des statistiques agrégées
sont produites (aucune colonne nominative : Chirurgien et Anesthésiste sont ignorées).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

DAYS = {"LUNDI": 0, "MARDI": 1, "MERCREDI": 2, "JEUDI": 3, "VENDREDI": 4, "SAMEDI": 5, "DIMANCHE": 6}
MIN_DUR, MAX_DUR = 3, 600  # filtrage des durées aberrantes (ex. 27 400 min)


def _anesth_family(label: str) -> str:
    s = str(label).lower()
    if s in {"-", "nan", ""}:
        return "inconnu"
    if "générale" in s or s.startswith("ag"):
        return "AG"
    if "sédation" in s:
        return "AL_sedation"
    if "locorégionale" in s or s in {"alr", "rachis", "bloc peripherique"}:
        return "ALR"
    if "locale" in s or s == "al":
        return "AL"
    return "autre"


def _minutes(hhmm) -> float | None:
    try:
        h, m = str(hhmm).split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def aggregate(path: Path) -> dict:
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    df = df.drop(columns=[c for c in ("Chirurgien", "Anesthésiste") if c in df.columns])  # données nominatives
    df["date"] = pd.to_datetime(df["Date"], dayfirst=True, format="mixed")
    df["weekday"] = df["Jour"].str.strip().str.upper().map(DAYS)
    total = len(df)
    cancelled = df[df["Statut"].str.strip() == "éliminé"]
    done = df[df["Statut"].str.strip() == "fermé"].copy()
    done = done[done["Salle"].str.startswith("OP")]
    n_outliers = int(((done["Durée"] < MIN_DUR) | (done["Durée"] > MAX_DUR)).sum())
    done = done[(done["Durée"] >= MIN_DUR) & (done["Durée"] <= MAX_DUR)]
    done["urgent"] = done["Type"].str.strip().str.lower().str.startswith("urg")
    done["start_min"] = done["Heure"].map(_minutes)
    done["anesth"] = done["Anesth réalisée"].map(_anesth_family)
    all_days = pd.date_range(df["date"].min(), df["date"].max(), freq="D")

    # volumes par jour de semaine (jours sans activité comptés à 0)
    per_day = done.groupby("date").size().reindex(all_days, fill_value=0)
    weekday_mean = per_day.groupby(per_day.index.weekday).mean().round(2).tolist()
    wk = per_day[per_day.index.weekday < 5]
    month_mean = wk.groupby(wk.index.month).mean().round(2).to_dict()

    # spécialités
    canc_by_spe = (df["Statut"].str.strip() == "éliminé").groupby(df["Spécialité"]).mean()
    specialties = {}
    for spe, g in done.groupby("Spécialité"):
        d = g["Durée"].astype(float)
        logd = np.log(d)
        specialties[spe] = {
            "n": int(len(g)),
            "share": round(len(g) / len(done), 4),
            "median_min": float(d.median()),
            "mean_min": round(float(d.mean()), 1),
            "sd_min": round(float(d.std(ddof=1)), 1) if len(g) > 1 else 0.0,
            "p10_min": float(d.quantile(0.1)),
            "p90_min": float(d.quantile(0.9)),
            "mu_log": round(float(logd.mean()), 4),
            "sigma_log": round(float(logd.std(ddof=1)), 4) if len(g) > 1 else 0.0,
            "urgent_share": round(float(g["urgent"].mean()), 4),
            "cancellation_rate": round(float(canc_by_spe.get(spe, 0.0)), 4),
            "ambulatory_share": round(float((g["Admission"].str.strip() == "Ambulatoire").mean()), 4),
            "anesthesia_mix": g["anesth"].value_counts(normalize=True).round(4).to_dict(),
            "rooms": g["Salle"].value_counts(normalize=True).round(4).to_dict(),
        }

    # salles : probabilité d'ouverture un jour de semaine, spécialités
    weekdays = [d for d in all_days if d.weekday() < 5]
    rooms = {}
    for room, g in done.groupby("Salle"):
        opened = g[g["weekday"] < 5]["date"].nunique()
        rooms[room] = {
            "open_rate_weekday": round(opened / len(weekdays), 4),
            "cases": int(len(g)),
            "specialties": g["Spécialité"].value_counts(normalize=True).round(4).to_dict(),
        }

    # délai de remise en état entre deux cas programmés d'une même salle
    prog = done[~done["urgent"]].sort_values(["Salle", "date", "start_min"]).copy()
    prog["end_min"] = prog["start_min"] + prog["Durée"]
    prog["next_start"] = prog.groupby(["Salle", "date"])["start_min"].shift(-1)
    gaps = (prog["next_start"] - prog["end_min"]).dropna()
    gaps = gaps[(gaps >= 0) & (gaps <= 120)]

    # premier cas programmé du matin
    first = prog[prog["weekday"] < 5].groupby(["Salle", "date"])["start_min"].min()

    hourly_prog = (prog["start_min"] // 60).value_counts(normalize=True).reindex(range(24), fill_value=0).round(4).tolist()
    urg = done[done["urgent"]]
    hourly_urg = (urg["start_min"] // 60).value_counts(normalize=True).reindex(range(24), fill_value=0).round(4).tolist()
    urg_per_day = urg.groupby("date").size().reindex(all_days, fill_value=0)

    reasons = cancelled["Raison Annulation"].dropna().str.strip().str.capitalize().value_counts().to_dict()
    return {
        "source": "Export OPROOM agrégé (aucune donnée nominative)",
        "period": {"start": str(df["date"].min().date()), "end": str(df["date"].max().date()), "days": len(all_days)},
        "totals": {
            "scheduled": total,
            "completed": int((df["Statut"].str.strip() == "fermé").sum()),
            "cancelled": int(len(cancelled)),
            "cancellation_rate": round(len(cancelled) / total, 4),
            "duration_outliers_removed": n_outliers,
            "completed_in_rooms_used": int(len(done)),
        },
        "targets": {
            "room_occupancy_rate": 0.47,
            "overflow_rate": 0.03,
            "first_incision_rate": 0.05,
            "turnover_median_min": float(gaps.median()),
            "first_case_start_median": f"{int(first.median()) // 60:02d}:{int(first.median()) % 60:02d}",
        },
        "weekday_mean_cases": weekday_mean,
        "month_mean_cases_weekdays": {int(k): v for k, v in month_mean.items()},
        "urgent": {
            "share_of_completed": round(float(done["urgent"].mean()), 4),
            "mean_per_day": round(float(urg_per_day.mean()), 2),
            "var_per_day": round(float(urg_per_day.var()), 2),
            "hourly_profile": hourly_urg,
        },
        "programmed_hourly_profile": hourly_prog,
        "admission_mix": done["Admission"].str.strip().value_counts(normalize=True).round(4).to_dict(),
        "anesthesia_mix": done["anesth"].value_counts(normalize=True).round(4).to_dict(),
        "cancellation_reasons": reasons,
        "specialties": specialties,
        "rooms": rooms,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()
    stats = aggregate(args.xlsx)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Statistiques écrites dans {args.output}")


if __name__ == "__main__":
    main()
