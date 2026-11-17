"""Orchestration de bout en bout, selon la chaîne d'agents du projet :

1. contrôle de complétude de la fiche (agent 1) + grille réglementaire Go/NoGo ;
2. normalisation de la fiche en paramètres de simulation (agent 2) ;
3. simulation du bloc « sans outil » et « avec outil » (agent 3) ;
4. effets humains : confiance, adoption, apprentissage, pannes (agent 4) ;
5. rapport lisible avec niveau de confiance et hypothèses (agent 5).

L'agent 1 est le seul à pouvoir arrêter la chaîne : fiche NON_ANALYSABLE = aucun résultat chiffré.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from .configurator import load_hospital
from .llm import LLMClient
from .models.fiche import FicheLogiciel
from .models.hospital import Hospital
from .models.scenario import Scenario
from .models.software import SoftwareModel
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
from .spec import FicheValidation, default_scenario, fiche_to_software, validate_document, validate_fiche
from .spec.completeness import Hypothese


class AuditResult(BaseModel):
    validation: FicheValidation
    hypotheses: list[Hypothese] = Field(default_factory=list)
    facts: AuditFacts
    narrative: ReportNarrative
    markdown: str
    html: str


def run_audit(
    hospital: Hospital | Path | str | dict,
    fiche: FicheLogiciel | Path | str,
    days: int = 28,
    replications: int = 10,
    seed: int = 42,
    workers: int = 1,
    extraction_llm: LLMClient | None = None,
    report_llm: LLMClient | None = None,
    software_override: SoftwareModel | None = None,
    simulate_even_if_not_analysable: bool = False,
    scenario: Scenario | None = None,
    human_factors: bool = True,
) -> AuditResult:
    h = hospital if isinstance(hospital, Hospital) else load_hospital(hospital)
    if isinstance(fiche, FicheLogiciel):
        validation = validate_fiche(fiche, llm=extraction_llm)
    else:
        validation = validate_document(Path(fiche), extraction_llm, known_task_kinds=h.documentation_kinds())

    sim = None
    hypotheses = list(validation.completude.hypotheses_necessaires)
    if validation.admissible or simulate_even_if_not_analysable:
        software, hyps = fiche_to_software(validation.fiche, h.documentation_kinds())
        software = software_override or software
        hypotheses += hyps
        sc = scenario or default_scenario(validation.fiche)
        if not human_factors:
            sc = sc.model_copy(update={"human": sc.human.model_copy(update={"enabled": False})})
        sim = simulate_audit(h, software, days=days, replications=replications, seed=seed, workers=workers, scenario=sc)

    score = compute_score(validation, sim)
    facts = build_facts(h, validation, score, sim, hypotheses)
    narrative = generate_narrative(facts, report_llm)
    return AuditResult(
        validation=validation,
        hypotheses=hypotheses,
        facts=facts,
        narrative=narrative,
        markdown=render_markdown(facts, narrative),
        html=render_html(facts, narrative),
    )
