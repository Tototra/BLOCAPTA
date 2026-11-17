"""Moteur de règles déterministe pour la validation des fiches techniques."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

from ..settings import get_settings

_MISSING = object()


class Condition(BaseModel):
    path: str
    op: Literal["present", "is_true", "contains_any", "in", "gte", "lte"]
    value: Any = None
    mode: Literal["any", "each"] = Field(
        default="any", description="Pour un chemin aplati ([]) : au moins un élément (any) ou tous (each)"
    )


class Criterion(BaseModel):
    id: str
    category: str
    label: str
    severity: Literal["bloquant", "majeur", "mineur"]
    when: Condition | None = None
    all: list[Condition] = Field(default_factory=list)
    any: list[Condition] = Field(default_factory=list)


class CriteriaSet(BaseModel):
    version: int = 1
    criteria: list[Criterion]


def load_criteria(path: Path | None = None) -> CriteriaSet:
    p = path or get_settings().criteria_file
    return CriteriaSet.model_validate(yaml.safe_load(Path(p).read_text(encoding="utf-8")))


def resolve(data: Any, path: str) -> list[Any] | Any:
    """Résout un chemin pointé. Si le chemin contient ``[]``, renvoie une liste aplatie."""
    flatten = "[]" in path
    current: list[Any] = [data]
    for part in path.split("."):
        is_list = part.endswith("[]")
        key = part[:-2] if is_list else part
        nxt: list[Any] = []
        for item in current:
            val = item.get(key, _MISSING) if isinstance(item, dict) else _MISSING
            if val is _MISSING:
                continue
            if is_list:
                nxt.extend(val or [])
            else:
                nxt.append(val)
        current = nxt
    if flatten:
        return current
    return current[0] if current else _MISSING


def _is_present(v: Any) -> bool:
    return v is not _MISSING and v is not None and v != "" and v != [] and v != {}


def _norm(s: Any) -> str:
    return str(s).replace(" ", "").replace("-", "").lower()


def _check_one(v: Any, cond: Condition) -> bool:
    if cond.op == "present":
        return _is_present(v)
    if cond.op == "is_true":
        return v is True
    if cond.op == "contains_any":
        items = v if isinstance(v, list) else [v]
        wanted = {_norm(x) for x in cond.value or []}
        return any(_norm(i) in wanted for i in items if _is_present(i))
    if cond.op == "in":
        return _is_present(v) and _norm(v) in {_norm(x) for x in cond.value or []}
    if cond.op == "gte":
        return _is_present(v) and v >= cond.value
    if cond.op == "lte":
        return _is_present(v) and v <= cond.value
    raise ValueError(cond.op)


def evaluate_condition(data: dict, cond: Condition) -> bool:
    v = resolve(data, cond.path)
    if "[]" in cond.path:
        values = v
        if cond.op == "contains_any":
            return _check_one(values, cond)
        if not values:
            return False
        checks = [_check_one(x, cond) for x in values]
        return all(checks) if cond.mode == "each" else any(checks)
    return _check_one(v, cond)


class CriterionResult(BaseModel):
    id: str
    category: str
    label: str
    severity: str
    status: Literal["ok", "echec", "non_applicable"]
    failed_paths: list[str] = Field(default_factory=list)


def evaluate(data: dict, criteria: CriteriaSet) -> list[CriterionResult]:
    results = []
    for c in criteria.criteria:
        if c.when and not evaluate_condition(data, c.when):
            results.append(CriterionResult(**c.model_dump(include={"id", "category", "label", "severity"}), status="non_applicable"))
            continue
        failed_all = [cond.path for cond in c.all if not evaluate_condition(data, cond)]
        any_ok = (not c.any) or any(evaluate_condition(data, cond) for cond in c.any)
        failed = failed_all + ([] if any_ok else [cond.path for cond in c.any])
        results.append(
            CriterionResult(
                **c.model_dump(include={"id", "category", "label", "severity"}),
                status="ok" if not failed else "echec",
                failed_paths=failed,
            )
        )
    return results
