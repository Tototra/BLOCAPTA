"""Validation du jumeau : la simulation de l'existant reproduit-elle la réalité observée ?"""

from __future__ import annotations

from pydantic import BaseModel

from ..calibration.builder import CalibrationReport
from ..models.hospital import Hospital
from .engine import SimulationOptions
from .montecarlo import run_replications, stat


class ValidationRow(BaseModel):
    kpi: str
    observed: float
    simulated: float
    ci_low: float
    ci_high: float
    error_pct: float
    ok: bool


class TwinValidation(BaseModel):
    valid: bool
    tolerance_pct: float
    rows: list[ValidationRow]


def validate_twin(
    hospital: Hospital,
    calibrations: list[CalibrationReport],
    days: int = 20,
    replications: int = 10,
    tolerance_pct: float = 10.0,
    seed: int = 1,
) -> TwinValidation:
    runs = run_replications(hospital, None, SimulationOptions(days=days, seed=seed), replications)
    rows = []
    for cal in calibrations:
        for kpi, observed in (
            (f"duree_parcours_moy_min.{cal.pathway_id}", cal.observed_mean_lead_time_min),
            (f"patients_par_jour.{cal.pathway_id}", cal.observed_mean_cases_per_day),
        ):
            s = stat([r.kpis.get(kpi, 0.0) for r in runs])
            err = 100 * abs(s.mean - observed) / observed if observed else 0.0
            rows.append(
                ValidationRow(
                    kpi=kpi, observed=observed, simulated=s.mean, ci_low=s.ci_low, ci_high=s.ci_high,
                    error_pct=round(err, 2), ok=err <= tolerance_pct,
                )
            )
    return TwinValidation(valid=all(r.ok for r in rows), tolerance_pct=tolerance_pct, rows=rows)
