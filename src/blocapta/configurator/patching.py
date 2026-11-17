"""Patchs de configuration (JSON Patch) + contrôles de cohérence.

Extension de la syntaxe JSON Pointer : ``/pathways[id=chirurgie]/steps[id=intervention]``
est résolu en index numérique avant application, ce qui rend les patchs lisibles
et robustes à l'ordre des éléments.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Literal

import jsonpatch
import jsonpointer
from pydantic import BaseModel, Field, ValidationError

from ..models.hospital import Hospital

_SELECTOR = re.compile(r"^(?P<key>[^\[]+)\[id=(?P<id>[^\]]+)\]$")


class PatchOp(BaseModel):
    op: Literal["add", "replace", "remove"]
    path: str = Field(description="JSON Pointer, ex. /resources/chirurgien/count ou /pathways[id=x]/arrivals")
    value_json: str | None = Field(default=None, description="Valeur encodée en JSON (sauf pour remove)")

    def value(self) -> Any:
        return None if self.value_json is None else json.loads(self.value_json)


class ConfigPatch(BaseModel):
    rationale: str = Field(default="", description="Pourquoi ces modifications")
    hypotheses: list[str] = Field(default_factory=list, description="Hypothèses faites faute d'information")
    operations: list[PatchOp] = Field(default_factory=list)


class PatchResult(BaseModel):
    ok: bool
    config: dict | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diff: list[str] = Field(default_factory=list)


def resolve_pointer(doc: dict, path: str, creating: bool = False) -> str:
    """Convertit les sélecteurs ``[id=…]`` d'un pointeur en index numériques."""
    parts = [p for p in path.split("/") if p != ""]
    out: list[str] = []
    node: Any = doc
    for i, part in enumerate(parts):
        m = _SELECTOR.match(part)
        if m:
            key, ident = m.group("key"), m.group("id")
            lst = node.get(key) if isinstance(node, dict) else None
            if not isinstance(lst, list):
                raise KeyError(f"'{key}' n'est pas une liste dans {path}")
            idx = next((j for j, it in enumerate(lst) if isinstance(it, dict) and it.get("id") == ident), None)
            if idx is None:
                raise KeyError(f"Aucun élément id='{ident}' dans '{key}'")
            out += [key, str(idx)]
            node = lst[idx]
        else:
            out.append(part)
            if isinstance(node, dict):
                node = node.get(part)
            elif isinstance(node, list) and part.isdigit():
                node = node[int(part)]
            elif not (creating and i == len(parts) - 1):
                node = None
    return "/" + "/".join(out)


def _ensure_parents(doc: dict, pointer: str) -> None:
    """Crée les dictionnaires intermédiaires manquants pour un ``add``."""
    parts = [p for p in pointer.split("/") if p != ""][:-1]
    node: Any = doc
    for p in parts:
        if isinstance(node, list):
            node = node[int(p)]
        else:
            if p not in node or node[p] is None:
                node[p] = {}
            node = node[p]


def sanity_warnings(h: Hospital) -> list[str]:
    """Contrôles métier non bloquants (ordres de grandeur)."""
    warns = []
    for p in h.pathways:
        per_day = p.arrivals.per_day.mean_value()
        for s in p.steps:
            for r, q in s.resources.items():
                pool = h.resources[r]
                hours = 24.0
                if pool.shift:
                    hours = ((pool.shift.end_min - pool.shift.start_min) % 1440) / 60 or 24.0
                demand = per_day * s.duration_min.mean_value() / 60 * q
                capacity = pool.count * hours
                if capacity and demand / capacity > 0.9:
                    warns.append(
                        f"'{p.id}/{s.id}' : la demande théorique sur '{r}' ({demand:.0f} h/j) dépasse 90 % "
                        f"de la capacité ({capacity:.0f} h/j) — saturation probable."
                    )
            if not s.duration_min.mean_value() > 0:
                warns.append(f"'{p.id}/{s.id}' : durée moyenne nulle")
    if not any(s.documentation for p in h.pathways for s in p.steps):
        warns.append("Aucune tâche de documentation modélisée : aucun logiciel ne pourra être évalué.")
    return warns


def _diff_lines(before: dict, after: dict) -> list[str]:
    ops = jsonpatch.make_patch(before, after).patch
    lines = []
    for o in ops:
        val = json.dumps(o.get("value"), ensure_ascii=False)[:120] if "value" in o else ""
        lines.append(f"{o['op']:7s} {o['path']} {val}".rstrip())
    return lines


def apply_patch(config: dict, operations: list[PatchOp]) -> PatchResult:
    doc = copy.deepcopy(config)
    try:
        raw_ops = []
        for op in operations:
            pointer = resolve_pointer(doc, op.path, creating=op.op == "add")
            if op.op == "add":
                _ensure_parents(doc, pointer)
            item: dict[str, Any] = {"op": op.op, "path": pointer}
            if op.op != "remove":
                item["value"] = op.value()
            raw_ops.append(item)
            doc = jsonpatch.apply_patch(doc, [item])
    except (KeyError, IndexError, ValueError, TypeError, jsonpatch.JsonPatchException, jsonpointer.JsonPointerException) as e:
        return PatchResult(ok=False, errors=[f"Patch inapplicable : {e}"])
    try:
        h = Hospital.model_validate(doc)
    except ValidationError as e:
        return PatchResult(ok=False, errors=[str(e)])
    return PatchResult(ok=True, config=doc, warnings=sanity_warnings(h), diff=_diff_lines(config, doc))
