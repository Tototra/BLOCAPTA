"""Chargement des configurations hôpital avec héritage d'archétypes.

Un fichier hôpital peut déclarer ``extends: ch_general`` : il hérite alors de
l'archétype et ne décrit que ses différences.

Règles de fusion :
- dictionnaires : fusion récursive ;
- listes d'objets possédant un ``id`` : fusion élément par élément sur l'``id`` ;
- autres listes et valeurs : remplacées ;
- ``{__delete__: true}`` supprime une clé ou un élément hérité.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from ..models.hospital import Hospital
from ..settings import get_settings

DELETE = "__delete__"


def _is_id_list(v: Any) -> bool:
    return isinstance(v, list) and v and all(isinstance(i, dict) and "id" in i for i in v)


def deep_merge(base: Any, override: Any) -> Any:
    if isinstance(override, dict) and override.get(DELETE):
        return DELETE
    if isinstance(base, dict) and isinstance(override, dict):
        out = copy.deepcopy(base)
        for k, v in override.items():
            merged = deep_merge(out.get(k), v) if k in out else deep_merge(None, v)
            if merged == DELETE:
                out.pop(k, None)
            else:
                out[k] = merged
        return out
    if _is_id_list(base) and _is_id_list(override):
        out = copy.deepcopy(base)
        index = {item["id"]: i for i, item in enumerate(out)}
        for item in override:
            if item["id"] in index:
                merged = deep_merge(out[index[item["id"]]], item)
                out[index[item["id"]]] = merged
            elif not item.get(DELETE):
                out.append(copy.deepcopy(item))
        return [i for i in out if i != DELETE]
    return copy.deepcopy(override)


def list_archetypes(directory: Path | None = None) -> dict[str, str]:
    d = directory or get_settings().archetypes_dir
    out = {}
    for f in sorted(Path(d).glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        out[f.stem] = data.get("name", f.stem)
    return out


def load_archetype_dict(name: str, directory: Path | None = None) -> dict:
    d = directory or get_settings().archetypes_dir
    path = Path(d) / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Archétype inconnu '{name}'. Disponibles : {list(list_archetypes(d))}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_dict(data: dict, directory: Path | None = None, _seen: tuple[str, ...] = ()) -> dict:
    parent_name = data.get("extends")
    if not parent_name:
        return copy.deepcopy(data)
    if parent_name in _seen:
        raise ValueError(f"Héritage circulaire : {' -> '.join((*_seen, parent_name))}")
    parent = resolve_dict(load_archetype_dict(parent_name, directory), directory, (*_seen, parent_name))
    merged = deep_merge(parent, {k: v for k, v in data.items() if k != "extends"})
    merged["extends"] = parent_name
    merged.setdefault("archetype", parent.get("archetype", parent_name))
    return merged


def load_hospital_dict(source: Path | str | dict, directory: Path | None = None) -> dict:
    if isinstance(source, dict):
        data = source
    else:
        data = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
    return resolve_dict(data, directory)


def load_hospital(source: Path | str | dict, directory: Path | None = None) -> Hospital:
    return Hospital.model_validate(load_hospital_dict(source, directory))


def dump_yaml(data: dict | Hospital) -> str:
    if isinstance(data, Hospital):
        data = data.model_dump(mode="json", exclude_none=True)
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)
