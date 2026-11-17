"""Vérification que chaque nombre cité par le LLM existe dans les faits de l'audit."""

from __future__ import annotations

import json
import re
from typing import Any

_NUM = re.compile(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w])")


def _walk(obj: Any, out: set[float]) -> None:
    if isinstance(obj, bool):
        return
    if isinstance(obj, int | float):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in _NUM.findall(obj):
            out.add(float(m.replace(",", ".")))
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _walk(k, out)
            _walk(v, out)
    elif isinstance(obj, list | tuple):
        for v in obj:
            _walk(v, out)


def allowed_numbers(facts: dict) -> set[float]:
    base: set[float] = set()
    _walk(facts, base)
    allowed = set(base)
    for v in base:
        for scale in (1, 100, 0.01, 60, 1 / 60):  # unités, pourcentages, minutes <-> heures
            x = v * scale
            allowed |= {round(x, 0), round(x, 1), round(x, 2), float(int(x))}
    allowed |= {float(i) for i in range(0, 11)}  # petits entiers (énumérations, « 2 saisies »)
    return allowed


def unverified_numbers(text: str, facts: dict, tolerance: float = 0.011) -> list[str]:
    allowed = allowed_numbers(facts)
    bad = []
    for m in _NUM.findall(text):
        v = float(m.replace(",", "."))
        if not any(abs(v - a) <= tolerance * max(1.0, abs(a)) for a in allowed):
            bad.append(m)
    return sorted(set(bad))


def facts_as_dict(facts) -> dict:
    return json.loads(facts.model_dump_json())
