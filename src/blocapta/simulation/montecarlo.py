"""Réplications Monte Carlo, comparaison baseline / logiciel, synthèse des frictions."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import stats

from ..models.hospital import Hospital
from ..models.results import FrictionSummary, KpiComparison, SimulationReport, Stat, StaticFinding
from ..models.software import SoftwareModel
from .engine import ReplicationResult, Simulation, SimulationOptions, kpi_label, software_gaps, task_key


def _one(args) -> ReplicationResult:
    hospital, software, options, i = args
    return Simulation(hospital, software, options, replication=i).run()


def run_replications(
    hospital: Hospital,
    software: SoftwareModel | None,
    options: SimulationOptions,
    replications: int,
    workers: int = 1,
) -> list[ReplicationResult]:
    jobs = [(hospital, software, options, i) for i in range(replications)]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            return list(ex.map(_one, jobs))
    return [_one(j) for j in jobs]


def stat(values: list[float], confidence: float = 0.95) -> Stat:
    x = np.asarray(values, dtype=float)
    n = len(x)
    mean = float(x.mean()) if n else 0.0
    if n < 2 or np.allclose(x, mean):
        return Stat(mean=round(mean, 4), ci_low=round(mean, 4), ci_high=round(mean, 4), n=n)
    half = float(stats.t.ppf((1 + confidence) / 2, n - 1) * x.std(ddof=1) / np.sqrt(n))
    return Stat(mean=round(mean, 4), ci_low=round(mean - half, 4), ci_high=round(mean + half, 4), n=n)


def compare(base: list[ReplicationResult], soft: list[ReplicationResult]) -> list[KpiComparison]:
    keys = sorted(set().union(*(r.kpis for r in base)) | set().union(*(r.kpis for r in soft)))
    out = []
    for k in keys:
        b = stat([r.kpis.get(k, 0.0) for r in base])
        s = stat([r.kpis.get(k, 0.0) for r in soft])
        label, unit = kpi_label(k)
        delta = round(s.mean - b.mean, 4)
        out.append(
            KpiComparison(
                kpi=k, label=label, unit=unit, baseline=b, software=s, delta=delta,
                delta_pct=round(100 * delta / b.mean, 2) if b.mean else None,
            )
        )
    return out


def _severity(ftype: str, hours_per_day: float, share: float, items_per_day: float) -> str:
    if (
        hours_per_day >= 1
        or items_per_day >= 1
        or (ftype == "interoperabilite" and share >= 0.5)
        or (ftype == "cardinalite" and share >= 0.3)
    ):
        return "critique"
    if hours_per_day >= 0.25 or share >= 0.2 or items_per_day > 0 or ftype in {"couverture", "interoperabilite"}:
        return "majeure"
    if share >= 0.02:
        return "mineure"
    return "info"


def summarise_frictions(runs: list[ReplicationResult]) -> list[FrictionSummary]:
    n = max(1, len(runs))
    groups: dict[tuple, list] = defaultdict(list)
    for r in runs:
        for f in r.frictions:
            groups[(f.type, f.pathway, f.step, f.role, f.task_kind)].append(f)
    total_tasks: dict[str, float] = defaultdict(float)
    for r in runs:
        for key, c in r.task_counts.items():
            total_tasks[key] += c
    days = float(np.mean([r.kpis.get("jours_actifs", 1.0) for r in runs])) if runs else 1.0
    out = []
    for (ftype, pw, step, role, kind), evs in groups.items():
        tasks = total_tasks.get(task_key(pw, step, role, kind), 0) or 1
        occ = len(evs) / n
        hours = sum(e.time_lost_min for e in evs) / 60 / n
        items = sum(e.items_at_risk for e in evs) / n
        # seules les omissions liées à la cardinalité sont des éléments « à risque » ;
        # pour la disponibilité il s'agit d'éléments saisis en différé
        risk_items = items if ftype == "cardinalite" else 0.0
        share = min(1.0, len(evs) / tasks)
        out.append(
            FrictionSummary(
                type=ftype, pathway=pw, step=step, role=role, task_kind=kind,
                occurrences_per_replication=round(occ, 2),
                affected_share=round(share, 4),
                time_lost_hours_per_replication=round(hours, 2),
                items_at_risk_per_replication=round(items, 2),
                occurrences_per_day=round(occ / days, 2),
                time_lost_hours_per_day=round(hours / days, 3),
                severity=_severity(ftype, hours / days, share, risk_items / days),
                example=evs[0].detail,
            )
        )
    order = {"critique": 0, "majeure": 1, "mineure": 2, "info": 3}
    return sorted(out, key=lambda f: (order[f.severity], -f.time_lost_hours_per_replication))


def static_analysis(hospital: Hospital, software: SoftwareModel) -> tuple[list[StaticFinding], list[str]]:
    """Vérifications qui ne nécessitent pas de simuler le temps."""
    findings: list[StaticFinding] = []
    kinds = hospital.documentation_kinds()
    unused = [tp.task_kind for tp in software.touchpoints if tp.task_kind not in kinds]
    for k in unused:
        findings.append(
            StaticFinding(
                type="couverture", severity="majeure",
                detail=f"La tâche '{k}' gérée par le logiciel n'existe dans aucun parcours modélisé de l'hôpital.",
            )
        )
    systems = {
        d.current_system
        for p in hospital.pathways
        for s in p.steps
        for d in s.documentation
        if d.kind in {tp.task_kind for tp in software.touchpoints}
    }
    for sys_id in sorted(systems):
        double, downstream = software_gaps(hospital, software, sys_id)
        cat = hospital.information_system.applications[sys_id].category
        if double:
            findings.append(
                StaticFinding(
                    type="interoperabilite", severity="critique",
                    detail=f"Aucun connecteur vers {cat} ('{sys_id}') : les données devront être ressaisies dans le système actuel.",
                )
            )
        for c in downstream:
            findings.append(
                StaticFinding(
                    type="interoperabilite", severity="info",
                    detail=f"Pas de connecteur direct vers {c} : le flux passera par '{sys_id}'.",
                )
            )
    if hospital.information_system.sso and software.sso is False:
        findings.append(
            StaticFinding(type="couverture", severity="majeure", detail="L'hôpital utilise un SSO mais le logiciel ne le supporte pas.")
        )
    for tp in software.touchpoints:
        for p in hospital.pathways:
            for s in p.steps:
                for d in s.documentation:
                    if d.kind == tp.task_kind and tp.max_items_per_entry:
                        mean_items = d.items.mean_value()
                        if mean_items > tp.max_items_per_entry:
                            findings.append(
                                StaticFinding(
                                    type="cardinalite", severity="majeure",
                                    detail=(
                                        f"'{p.id}/{s.id}' : {mean_items:.2f} éléments en moyenne par tâche '{d.kind}' "
                                        f"pour un maximum de {tp.max_items_per_entry} par saisie."
                                    ),
                                )
                            )
    return findings, unused


def simulate_audit(
    hospital: Hospital,
    software: SoftwareModel,
    days: int = 20,
    replications: int = 20,
    seed: int = 42,
    workers: int = 1,
) -> SimulationReport:
    options = SimulationOptions(days=days, seed=seed)
    base = run_replications(hospital, None, options, replications, workers)
    soft = run_replications(hospital, software, options, replications, workers)
    findings, unused = static_analysis(hospital, software)
    return SimulationReport(
        hospital_id=hospital.id,
        software_name=software.name,
        days=days,
        replications=replications,
        seed=seed,
        kpis=compare(base, soft),
        frictions=summarise_frictions(soft),
        static_findings=findings,
        unused_touchpoints=unused,
    )
