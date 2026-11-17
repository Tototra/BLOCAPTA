"""Orchestration de bout en bout : fiche technique → validation → simulation → rapport."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from .configurator import load_hospital
from .llm import LLMClient
from .models.hospital import Hospital
from .models.software import SoftwareModel
from .models.spec_sheet import SpecSheet
from .reporting import (
    AuditFacts,
    ReportNarrative,
    build_facts,
    compute_score,
    generate_narrative,
    render_html,
    render_markdown,
)
from .simulation import simulate_audit
from .spec import SpecValidation, validate_document, validate_spec


class AuditResult(BaseModel):
    validation: SpecValidation
    facts: AuditFacts
    narrative: ReportNarrative
    markdown: str
    html: str


def run_audit(
    hospital: Hospital | Path | str | dict,
    spec: SpecSheet | Path | str,
    days: int = 20,
    replications: int = 20,
    seed: int = 42,
    workers: int = 1,
    extraction_llm: LLMClient | None = None,
    report_llm: LLMClient | None = None,
    software_override: SoftwareModel | None = None,
    simulate_even_if_not_admissible: bool = False,
) -> AuditResult:
    h = hospital if isinstance(hospital, Hospital) else load_hospital(hospital)
    if isinstance(spec, SpecSheet):
        validation = validate_spec(spec)
    else:
        validation = validate_document(Path(spec), extraction_llm, known_task_kinds=h.documentation_kinds())

    sim = None
    if validation.admissible or simulate_even_if_not_admissible:
        software = software_override or SoftwareModel.from_spec_sheet(validation.spec)
        sim = simulate_audit(h, software, days=days, replications=replications, seed=seed, workers=workers)

    score = compute_score(validation, sim)
    facts = build_facts(h, validation, score, sim)
    narrative = generate_narrative(facts, report_llm)
    return AuditResult(
        validation=validation,
        facts=facts,
        narrative=narrative,
        markdown=render_markdown(facts, narrative),
        html=render_html(facts, narrative),
    )
