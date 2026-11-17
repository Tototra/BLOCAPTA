"""Chargement d'un journal d'événements horodatés (export brancardage, bloc, ADT…).

Format pivot (une ligne = un événement) :
    case_id, activity, timestamp [, resource] [, role] [, pathway]
Les noms de colonnes réels de l'hôpital sont mappés via ``ColumnMapping``.
"""

from __future__ import annotations

import re
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


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _parse_timestamps(col: pd.Series, mapping: ColumnMapping) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(col):
        return col
    if mapping.timestamp_format:
        return pd.to_datetime(col, format=mapping.timestamp_format)
    sample = col.dropna().astype(str).head(50)
    if len(sample) and sample.str.match(_ISO).all():
        return pd.to_datetime(col, format="ISO8601")
    return pd.to_datetime(col, dayfirst=mapping.dayfirst, format="mixed")


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
    df["timestamp"] = _parse_timestamps(df["timestamp"], mapping)
    df["case_id"] = df["case_id"].astype(str)
    df["activity"] = df["activity"].astype(str).str.strip()
    df = df.dropna(subset=["timestamp"]).sort_values(["case_id", "timestamp"], kind="stable")
    return df.reset_index(drop=True)
