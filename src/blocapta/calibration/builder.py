"""Construction d'un parcours calibré à partir d'un journal d'événements."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field

from ..models.hospital import Arrivals, DocumentationTask, Pathway, Step, TimeWindow
from .discovery import arrival_stats, transition_durations, variants
from .fitting import fit_count, fit_duration


class StepFit(BaseModel):
    step: str
    transition: str
    distribution: str
    n: int
    mean_observed_min: float
    aic: float | None
    ks_pvalue: float | None


class CalibrationReport(BaseModel):
    pathway_id: str
    cases: int
    main_variant: list[str]
    main_variant_share: float
    variants_count: int
    observed_mean_lead_time_min: float
    observed_mean_cases_per_day: float
    steps: list[StepFit] = Field(default_factory=list)


def build_pathway(
    df: pd.DataFrame,
    pathway_id: str,
    service: str,
    step_resources: dict[str, dict[str, int]] | None = None,
    step_documentation: dict[str, list[dict]] | None = None,
) -> tuple[Pathway, CalibrationReport]:
    """Calibre un parcours sur la variante principale du journal.

    ``step_resources`` : activité -> ressources mobilisées pendant l'étape qui commence à cette activité.
    ``step_documentation`` : activité -> tâches de documentation déclenchées à la fin de l'étape.
    """
    step_resources = step_resources or {}
    step_documentation = step_documentation or {}
    vs = variants(df)
    if not vs:
        raise ValueError("Journal vide")
    main = vs[0]
    trans = transition_durations(df)
    steps: list[Step] = []
    fits: list[StepFit] = []
    acts = main.activities
    for a, b in zip(acts[:-1], acts[1:], strict=True):
        samples = trans.loc[(trans.activity == a) & (trans.next_activity == b), "duration_min"]
        fit = fit_duration(samples)
        steps.append(
            Step(
                id=a,
                label=f"{a} → {b}",
                duration_min=fit.distribution,
                resources=step_resources.get(a, {}),
                documentation=[DocumentationTask.model_validate(d) for d in step_documentation.get(a, [])],
            )
        )
        fits.append(
            StepFit(
                step=a,
                transition=f"{a}→{b}",
                distribution=fit.name,
                n=fit.n,
                mean_observed_min=round(float(samples.mean()), 2),
                aic=fit.aic,
                ks_pvalue=fit.ks_pvalue,
            )
        )
    arr = arrival_stats(df)
    pathway = Pathway(
        id=pathway_id,
        service=service,
        arrivals=Arrivals(
            per_day=fit_count(arr.daily_counts),
            window=TimeWindow(start=arr.window_start, end=arr.window_end, weekdays=arr.weekdays),
            hourly_profile=arr.hourly_profile if sum(arr.hourly_profile) > 0 else None,
        ),
        steps=steps,
    )
    lead = df.groupby("case_id")["timestamp"].agg(lambda s: (s.max() - s.min()).total_seconds() / 60)
    report = CalibrationReport(
        pathway_id=pathway_id,
        cases=int(df.case_id.nunique()),
        main_variant=list(acts),
        main_variant_share=round(main.share, 4),
        variants_count=len(vs),
        observed_mean_lead_time_min=round(float(lead.mean()), 2),
        observed_mean_cases_per_day=round(arr.mean_per_day, 2),
        steps=fits,
    )
    return pathway, report
