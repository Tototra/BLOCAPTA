"""Questionnaire DSI : génération du template et application des réponses."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from ..llm import LLMClient
from ..settings import get_settings
from .assistant import propose_patch
from .loader import load_archetype_dict, resolve_dict
from .patching import PatchOp, PatchResult, apply_patch

_DAYS = {"lun": 0, "mar": 1, "mer": 2, "jeu": 3, "ven": 4, "sam": 5, "dim": 6}


class Question(BaseModel):
    id: str
    question: str
    help: str | None = None
    example: str | None = None
    unit: str | None = None
    transform: str = "text"
    maps_to: str | list[str] | None = None
    required: bool = False

    @property
    def targets(self) -> list[str]:
        if self.maps_to is None:
            return []
        return [self.maps_to] if isinstance(self.maps_to, str) else list(self.maps_to)


class Section(BaseModel):
    id: str
    title: str
    questions: list[Question]


class Questionnaire(BaseModel):
    title: str
    version: int = 1
    intro: str = ""
    sections: list[Section]

    def questions(self) -> list[Question]:
        return [q for s in self.sections for q in s.questions]


def load_questionnaire(path: Path | None = None) -> Questionnaire:
    p = path or get_settings().questionnaire_file
    return Questionnaire.model_validate(yaml.safe_load(Path(p).read_text(encoding="utf-8")))


def render_markdown(q: Questionnaire) -> str:
    lines = [f"# {q.title}", "", q.intro.strip(), ""]
    lines += ["> Renvoyez vos réponses dans le fichier `reponses.yaml` (généré par `blocapta template --answers`).", ""]
    for s in q.sections:
        lines += [f"## {s.id}. {s.title}", "", "| Réf. | Question | Format / exemple | Réponse |", "|---|---|---|---|"]
        for qu in s.questions:
            fmt = qu.example or qu.transform
            if qu.unit:
                fmt += f" ({qu.unit})"
            label = qu.question + (" **(obligatoire)**" if qu.required else "")
            if qu.help:
                label += f"<br><sub>{qu.help}</sub>"
            lines.append(f"| {qu.id} | {label} | `{fmt}` | |")
        lines.append("")
    return "\n".join(lines)


def answers_template(q: Questionnaire) -> str:
    out = [f"# Réponses — {q.title}", "# Laissez null si l'information est inconnue.", "archetype: ch_general", "answers:"]
    for s in q.sections:
        out.append(f"  # --- {s.id}. {s.title}")
        for qu in s.questions:
            ex = f"  # ex. {qu.example}" if qu.example else ""
            out.append(f"  {qu.id}: null    # {qu.question}{ex}")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ transforms
def _parse(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if s[:1] in "[{":
            try:
                return yaml.safe_load(s)
            except yaml.YAMLError:
                return value
    return value


def _weekdays(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(v) for v in value]
    s = str(value).lower().strip()
    m = re.match(r"(\w{3})\w*\s*[-–à]\s*(\w{3})", s)
    if m:
        a, b = _DAYS[m.group(1)], _DAYS[m.group(2)]
        return list(range(a, b + 1))
    return [_DAYS[d[:3]] for d in re.split(r"[,\s]+", s) if d[:3] in _DAYS]


def _time(value: Any) -> str:
    m = re.match(r"(\d{1,2})[:h](\d{2})?", str(value).strip())
    if not m:
        raise ValueError(f"heure invalide : {value}")
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"


def transform_value(transform: str, value: Any) -> Any:
    v = _parse(value)
    if transform == "int":
        return int(float(v))
    if transform == "float":
        return float(v)
    if transform == "bool":
        return v if isinstance(v, bool) else str(v).strip().lower() in {"oui", "yes", "true", "1", "vrai"}
    if transform == "time":
        return _time(v)
    if transform == "time_window":
        start, end = re.split(r"\s*[-–]\s*|\s+à\s+", str(v).strip(), maxsplit=1)
        return {"start": _time(start), "end": _time(end)}
    if transform == "weekdays":
        return _weekdays(v)
    if transform == "poisson":
        return {"dist": "poisson", "lam": float(v)}
    if transform == "lognormal":
        if isinstance(v, dict):
            return {"dist": "lognormal", "mean": float(v["mean"]), "sd": float(v["sd"])}
        mean, sd = v
        return {"dist": "lognormal", "mean": float(mean), "sd": float(sd)}
    if transform == "empirical":
        return {"dist": "empirical", "values": {str(float(k)): float(p) for k, p in dict(v).items()}}
    if transform == "seconds_to_fixed_minutes":
        return {"dist": "fixed", "value": float(v) / 60}
    if transform == "triangular_minutes":
        low, mode, high = (float(x) for x in v)
        return {"dist": "triangular", "low": low, "mode": mode, "high": high}
    if transform == "list":
        return v if isinstance(v, list) else [x.strip() for x in str(v).split(",") if x.strip()]
    return str(v)


class AnswersResult(BaseModel):
    config: dict | None
    applied: list[str] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    context_notes: dict[str, str] = Field(default_factory=dict)
    llm_hypotheses: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)


def _is_unknown(v: Any) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in {"", "inconnu", "nc", "n/a", "?"})


def apply_answers(
    answers: dict[str, Any],
    archetype: str = "ch_general",
    questionnaire: Questionnaire | None = None,
    llm: LLMClient | None = None,
    hospital_id: str | None = None,
) -> AnswersResult:
    q = questionnaire or load_questionnaire()
    config = resolve_dict(load_archetype_dict(archetype))
    config["extends"] = None
    config["archetype"] = archetype
    config["id"] = hospital_id or "hopital"
    res = AnswersResult(config=None)

    for qu in q.questions():
        raw = answers.get(qu.id)
        if _is_unknown(raw):
            if qu.required:
                res.missing_required.append(f"{qu.id} — {qu.question}")
            continue
        if not qu.targets:
            res.context_notes[qu.id] = f"{qu.question} : {raw}"
            continue
        try:
            value = transform_value(qu.transform, raw)
        except (ValueError, TypeError, KeyError) as e:
            res.errors.append(f"{qu.id} : réponse '{raw}' illisible ({e})")
            continue
        for target in qu.targets:
            if qu.transform == "time_window":
                ops = [
                    PatchOp(op="add", path=f"{target}/start", value_json=json.dumps(value["start"])),
                    PatchOp(op="add", path=f"{target}/end", value_json=json.dumps(value["end"])),
                ]
            else:
                ops = [PatchOp(op="add", path=target, value_json=json.dumps(value, ensure_ascii=False))]
            r = apply_patch(config, ops)
            if r.ok:
                config = r.config
                res.applied.append(f"{qu.id} → {target}")
            else:
                res.errors.append(f"{qu.id} → {target} : {'; '.join(r.errors)[:300]}")

    if res.context_notes and llm is not None:
        instruction = (
            "Mets à jour la configuration pour refléter ces informations fournies par la DSI "
            "(n'invente rien de non mentionné) :\n" + "\n".join(res.context_notes.values())
        )
        patch, r = propose_patch(config, instruction, llm)
        if r.ok:
            config = r.config
            res.llm_hypotheses = patch.hypotheses
            res.applied += [f"LLM : {line}" for line in r.diff]
        else:
            res.errors += [f"LLM : {e}" for e in r.errors]
    for k, note in res.context_notes.items():
        config.setdefault("metadata", {})[f"note_{k}"] = note[:500]

    final = apply_patch(config, [])
    res.config = final.config if final.ok else config
    res.warnings = final.warnings
    if not final.ok:
        res.errors += final.errors
    return res


def apply_answers_file(path: Path, llm: LLMClient | None = None) -> AnswersResult:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return apply_answers(
        data.get("answers", {}), archetype=data.get("archetype", "ch_general"), llm=llm, hospital_id=data.get("id")
    )


__all__ = [
    "AnswersResult",
    "PatchResult",
    "Questionnaire",
    "answers_template",
    "apply_answers",
    "apply_answers_file",
    "load_questionnaire",
    "render_markdown",
    "transform_value",
]
