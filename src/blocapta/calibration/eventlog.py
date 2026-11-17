"""Chargement d'un journal d'événements horodatés (export brancardage, bloc, ADT…).

Format pivot (une ligne = un événement) :
    case_id, activity, timestamp [, resource] [, role] [, pathway]
Les noms de colonnes réels de l'hôpital sont mappés via ``ColumnMapping``.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from pydantic import BaseModel


class ColumnMapping(BaseModel):
    case_id: str = "case_id"
    activity: str = "activity"
    timestamp: str = "timestamp"
    resource: str | None = "resource"
    role: str | None = "role"
    pathway: str | None = "pathway"
    timestamp_format: str | None = None
    dayfirst: bool = True


REQUIRED = ("case_id", "activity", "timestamp")


def load_event_log(path: Path | str, mapping: ColumnMapping | None = None, sep: str | None = None) -> pd.DataFrame:
    mapping = mapping or ColumnMapping()
    path = Path(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        raw = pd.read_excel(path)
    else:
        raw = pd.read_csv(path, sep=sep, engine="python")
    return normalise(raw, mapping)


def normalise(raw: pd.DataFrame, mapping: ColumnMapping) -> pd.DataFrame:
    rename = {}
    for target in ("case_id", "activity", "timestamp", "resource", "role", "pathway"):
        src = getattr(mapping, target)
        if src and src in raw.columns:
            rename[src] = target
    df = raw.rename(columns=rename)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes obligatoires absentes : {missing}. Colonnes disponibles : {list(raw.columns)}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], format=mapping.timestamp_format, dayfirst=mapping.dayfirst)
    df["case_id"] = df["case_id"].astype(str)
    df["activity"] = df["activity"].astype(str).str.strip()
    df = df.dropna(subset=["timestamp"]).sort_values(["case_id", "timestamp"], kind="stable")
    return df.reset_index(drop=True)
