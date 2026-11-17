"""Test de fidélité (cahier des charges, test n° 1) : le bloc simulé SANS outil
retrouve-t-il les chiffres réels ? Règle Stop/Go : tant qu'un indicateur clé s'écarte
de plus de 10 %, on ne teste aucun logiciel.

Contrôles physiques associés (checklist « Bug catching ») : aucune unité à deux endroits,
aucune durée négative, occupation comprise entre 0 et 100 %.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..models.hospital import Hospital
from .engine import WEEKDAY_LABELS, SimulationOptions
from .montecarlo import run_replications, stat


class FidelityRow(BaseModel):
    indicator: str
    observed: float
    simulated: float
    ci_low: float
    ci_high: float
    error_pct: float
    tolerance: str
    ok: bool


class FidelityReport(BaseModel):
    verdict: str = Field(description="GO si tous les indicateurs et contrôles passent, sinon STOP")
    rows: list[FidelityRow]
    invariants: dict[str, float]
    invariants_ok: bool
    days: int
    replications: int


def _row(name: str, observed: float, values: list[float], rel_tol: float, abs_tol: float | None = None) -> FidelityRow:
    s = stat(values)
    err = 100 * abs(s.mean - observed) / observed if observed else 0.0
    if abs_tol is not None:
        ok = abs(s.mean - observed) <= abs_tol
        tol = f"± {abs_tol:g} pt"
    else:
        ok = err <= rel_tol * 100
        tol = f"± {rel_tol:.0%}"
    return FidelityRow(
        indicator=name, observed=round(observed, 2), simulated=round(s.mean, 2), ci_low=round(s.ci_low, 2),
        ci_high=round(s.ci_high, 2), error_pct=round(err, 1), tolerance=tol, ok=ok,
    )


def check_fidelity(
    hospital: Hospital,
    targets: dict,
    days: int = 56,
    replications: int = 10,
    seed: int = 7,
    rel_tol: float = 0.10,
    workers: int = 1,
) -> FidelityReport:
    runs = run_replications(hospital, None, SimulationOptions(days=days, seed=seed), replications, workers)
    rows: list[FidelityRow] = []

    def col(key: str) -> list[float]:
        return [r.kpis[key] for r in runs if key in r.kpis]

    if "interventions_par_jour_ouvre" in targets:
        per_run = [
            sum(r.kpis.get(f"interventions_par_jour.{d}", 0.0) for d in WEEKDAY_LABELS[:5]) / 5 for r in runs
        ]
        rows.append(_row("Interventions réalisées par jour ouvré", targets["interventions_par_jour_ouvre"], per_run, rel_tol))
    if "taux_annulation_pct" in targets:
        rows.append(_row("Taux d'annulation (%)", targets["taux_annulation_pct"], col("taux_annulation_pct"), rel_tol))
    if "occupation_salles_pct" in targets:
        # définition OPROOM à confirmer : temps patient / (toutes les salles × vacation programmée)
        key = "occupation_capacite_pct" if col("occupation_capacite_pct") else "occupation_salles_pct"
        rows.append(_row("Taux d'occupation des salles (%)", targets["occupation_salles_pct"], col(key), rel_tol))
    if "heure_premier_cas_min" in targets:
        rows.append(
            _row("Heure du premier cas (min depuis minuit)", targets["heure_premier_cas_min"], col("heure_premier_cas_min"), rel_tol)
        )
    if "taux_debordement_pct" in targets:
        rows.append(
            _row("Taux de débordement (%)", targets["taux_debordement_pct"], col("taux_debordement_pct"), rel_tol, abs_tol=2.0)
        )
    by_specialty = {p.specialty: p.id for p in hospital.pathways if p.specialty and not p.urgent}
    for spe, median in targets.get("duree_mediane_par_specialite_min", {}).items():
        pid = by_specialty.get(spe)
        if pid and col(f"duree_mediane_cas_min.{pid}"):
            rows.append(_row(f"Durée médiane – {spe} (min)", median, col(f"duree_mediane_cas_min.{pid}"), rel_tol))

    invariants = {
        "controle_ubiquite": max(col("controle_ubiquite") or [0.0]),
        "durees_negatives": max(col("durees_negatives") or [0.0]),
        "occupation_max_pct": max(
            [v for r in runs for k, v in r.kpis.items() if k == "occupation_salles_pct"] or [0.0]
        ),
    }
    inv_ok = invariants["controle_ubiquite"] == 0 and invariants["durees_negatives"] == 0 and invariants["occupation_max_pct"] <= 100
    verdict = "GO" if inv_ok and all(r.ok for r in rows) else "STOP"
    return FidelityReport(
        verdict=verdict, rows=rows, invariants=invariants, invariants_ok=inv_ok, days=days, replications=replications
    )
