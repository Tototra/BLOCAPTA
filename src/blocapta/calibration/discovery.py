"""Process mining léger : variantes de parcours, graphe direct-follows, arrivées.

Suffisant pour calibrer le jumeau. Pour des analyses plus poussées, le même
DataFrame peut être passé tel quel à PM4Py (colonnes renommées en case:concept:name…).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Variant:
    activities: tuple[str, ...]
    count: int
    share: float


def variants(df: pd.DataFrame) -> list[Variant]:
    seqs = df.groupby("case_id", sort=False)["activity"].apply(tuple)
    counts = seqs.value_counts()
    total = int(counts.sum())
    return [Variant(activities=k, count=int(v), share=v / total) for k, v in counts.items()]


def transition_durations(df: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par transition A→B dans un même cas, avec la durée en minutes."""
    d = df[["case_id", "activity", "timestamp"]].copy()
    d["next_activity"] = d.groupby("case_id")["activity"].shift(-1)
    d["next_timestamp"] = d.groupby("case_id")["timestamp"].shift(-1)
    d = d.dropna(subset=["next_activity"])
    d["duration_min"] = (d["next_timestamp"] - d["timestamp"]).dt.total_seconds() / 60
    return d[["case_id", "activity", "next_activity", "duration_min", "timestamp"]]


def directly_follows(df: pd.DataFrame) -> pd.DataFrame:
    t = transition_durations(df)
    return (
        t.groupby(["activity", "next_activity"])["duration_min"]
        .agg(count="count", mean="mean", median="median", p90=lambda s: s.quantile(0.9))
        .reset_index()
        .sort_values("count", ascending=False)
    )


@dataclass
class ArrivalStats:
    daily_counts: list[int]
    mean_per_day: float
    var_per_day: float
    weekdays: list[int]
    hourly_profile: list[float]
    window_start: str
    window_end: str


def arrival_stats(df: pd.DataFrame, min_day_share: float = 0.05) -> ArrivalStats:
    first = df.groupby("case_id")["timestamp"].min()
    by_day = first.dt.normalize().value_counts()
    weekday_share = first.dt.weekday.value_counts(normalize=True)
    weekdays = sorted(int(d) for d in weekday_share.index if weekday_share[d] >= min_day_share)
    # inclut les jours actifs sans arrivée (comptés 0) pour ne pas biaiser la moyenne
    all_days = pd.date_range(by_day.index.min(), by_day.index.max(), freq="D")
    active_days = [d for d in all_days if d.weekday() in weekdays]
    counts = [int(by_day.get(d, 0)) for d in active_days]
    hours = first.dt.hour.value_counts().reindex(range(24), fill_value=0)
    profile = (hours / hours.sum()).round(4).tolist()
    minutes = first.dt.hour * 60 + first.dt.minute
    lo, hi = np.percentile(minutes, [1, 99])
    hi = min(hi + 1, 1439)
    return ArrivalStats(
        daily_counts=counts,
        mean_per_day=float(np.mean(counts)),
        var_per_day=float(np.var(counts)),
        weekdays=weekdays,
        hourly_profile=profile,
        window_start=f"{int(lo) // 60:02d}:{int(lo) % 60:02d}",
        window_end=f"{int(hi) // 60:02d}:{int(hi) % 60:02d}",
    )
