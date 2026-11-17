"""Réplications Monte Carlo, comparaison baseline / logiciel, synthèse des frictions."""

from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy import stats

from ..models.hospital import Hospital
from ..models.results import (
    FrictionSummary,
    HumanSummary,
    KpiComparison,
    SimulationReport,
    Stat,
    StaticFinding,
)
from ..models.software import SoftwareModel
from .engine import ReplicationResult, Simulation, SimulationOptions, kpi_label, software_gaps


def _one(args) -> ReplicationResult:
    hospital, software, options, i, scenario = args
    return Simulation(hospital, software, options, replication=i, scenario=scenario).run()


def run_replications(
    hospital: Hospital,
    software: SoftwareModel | None,
    options: SimulationOptions,
    replications: int,
    workers: int = 1,
    scenario=None,
) -> list[ReplicationResult]:
    jobs = [(hospital, software, options, i, scenario) for i in range(replications)]
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


def summarise_frictions(runs: list[ReplicationResult], hospital: Hospital | None = None) -> list[FrictionSummary]:
    """Agrège les frictions par (type, tâche, métier) : une friction de même nature vécue dans
    plusieurs parcours (ex. toutes les spécialités) n'est comptée qu'une fois, avec son ampleur totale."""
    n = max(1, len(runs))

    def family(pool: str) -> str:
        if hospital is not None and pool in hospital.resources and hospital.resources[pool].role:
            return hospital.resources[pool].role
        return pool

    groups: dict[tuple, list] = defaultdict(list)
    for r in runs:
        for f in r.frictions:
            groups[(f.type, f.task_kind, family(f.role))].append(f)
    total_tasks: dict[tuple, float] = defaultdict(float)
    for r in runs:
        for key, c in r.task_counts.items():
            pw, step, role, kind = key.split("|")
            total_tasks[(kind, family(role))] += c
    days = float(np.mean([r.kpis.get("jours_actifs", 1.0) for r in runs])) if runs else 1.0
    out = []
    for (ftype, kind, fam), evs in groups.items():
        tasks = total_tasks.get((kind, fam), 0) or 1
        occ = len(evs) / n
        hours = sum(e.time_lost_min for e in evs) / 60 / n
        items = sum(e.items_at_risk for e in evs) / n
        risk_items = items if ftype == "cardinalite" else 0.0
        share = min(1.0, len(evs) / tasks)
        pathways = {e.pathway for e in evs}
        steps = defaultdict(int)
        for e in evs:
            steps[e.step] += 1
        out.append(
            FrictionSummary(
                type=ftype,
                pathway=next(iter(pathways)) if len(pathways) == 1 else f"{len(pathways)} parcours",
                step=max(steps, key=steps.get),
                role=fam,
                task_kind=kind,
                occurrences_per_replication=round(occ, 2),
                affected_share=round(share, 4),
                time_lost_hours_per_replication=round(hours, 2),
                items_at_risk_per_replication=round(items, 2),
                occurrences_per_day=round(occ / days, 2),
                time_lost_hours_per_day=round(hours / days, 3),
                severity=_severity(ftype, hours / days, share, risk_items / days),
                example=max(evs, key=lambda e: e.time_lost_min).detail,
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
        if not tp.max_items_per_entry:
            continue
        over: dict[float, list[str]] = defaultdict(list)
        for p in hospital.pathways:
            for s in p.steps:
                for d in s.documentation:
                    if d.kind == tp.task_kind and d.items.mean_value() > tp.max_items_per_entry:
                        over[round(d.items.mean_value(), 2)].append(p.label or p.id)
        for mean_items, where in sorted(over.items(), reverse=True):
            scope = where[0] if len(where) == 1 else f"{len(where)} parcours"
            findings.append(
                StaticFinding(
                    type="cardinalite", severity="majeure",
                    detail=(
                        f"{scope} : {mean_items:.2f} éléments en moyenne par tâche '{tp.task_kind}' "
                        f"pour un maximum de {tp.max_items_per_entry} par saisie."
                    ),
                )
            )
    return findings, unused


def summarise_human(runs: list[ReplicationResult], scenario) -> HumanSummary | None:
    hs = [r.human for r in runs if r.human]
    if not hs:
        return None
    roles = sorted({role for h in hs for role in h["trust_by_day"]})
    families = sorted({f for h in hs for f in h.get("trust_by_family", {})})
    trust_by_family = {}
    for fam in families:
        series = [h["trust_by_family"].get(fam, []) for h in hs]
        n_f = min(len(x) for x in series) if series else 0
        trust_by_family[fam] = [round(float(np.mean([x[d] for x in series])), 4) for d in range(n_f)]
    usage_family = {}
    for fam in families:
        u = [h["usage_by_family"][fam] for h in hs if fam in h.get("usage_by_family", {})]
        if u:
            usage_family[fam] = round(float(np.mean(u)), 2)
    trust_by_day = {}
    for role in roles:
        series = [h["trust_by_day"].get(role, []) for h in hs]
        n = min(len(x) for x in series) if series else 0
        trust_by_day[role] = [round(float(np.mean([x[d] for x in series])), 4) for d in range(n)]
    weeks = min(len(h["sw_minutes_by_week"]) for h in hs)
    special = {}
    for name in sorted({k for h in hs for k in h.get("special_agents", {})}):
        series = [h["special_agents"][name] for h in hs if name in h.get("special_agents", {})]
        n = min(len(x) for x in series)
        special[name] = [round(float(np.mean([x[d] for x in series])), 4) for d in range(n)]
    usage = {}
    final = {}
    for role in roles:
        u = [r.kpis[f"taux_utilisation_outil.{role}"] for r in runs if f"taux_utilisation_outil.{role}" in r.kpis]
        if u:
            usage[role] = round(float(np.mean(u)), 2)
        f = [r.kpis[f"confiance_moyenne.{role}"] for r in runs if f"confiance_moyenne.{role}" in r.kpis]
        if f:
            final[role] = round(float(np.mean(f)), 4)
    cfg = scenario.human
    return HumanSummary(
        roles=roles,
        trust_by_day=trust_by_day,
        trust_by_family=trust_by_family,
        usage_by_family=usage_family,
        special_agents=special,
        usage_rate_by_role=usage,
        final_trust_by_role=final,
        sw_minutes_by_week=[round(float(np.mean([h["sw_minutes_by_week"][w] for h in hs])), 3) for w in range(weeks)],
        outages=round(float(np.mean([h["outages"] for h in hs])), 2),
        outage_minutes=round(float(np.mean([h["outage_minutes"] for h in hs])), 1),
        parameters={
            "lambda (aversion à la perte)": cfg.loss_aversion,
            "alpha (apprentissage) — à calibrer": cfg.alpha,
            "kappa (influence des collègues) — à calibrer": cfg.kappa,
            "confiance initiale — à calibrer": cfg.initial_trust,
            "seuil de contournement — à calibrer": cfg.bypass_threshold,
            "facteur du 1er usage — à calibrer": cfg.learning_initial_factor,
        },
    )


def simulate_audit(
    hospital: Hospital,
    software: SoftwareModel,
    days: int = 20,
    replications: int = 20,
    seed: int = 42,
    workers: int = 1,
    scenario=None,
) -> SimulationReport:
    options = SimulationOptions(days=days, seed=seed)
    if scenario is not None and scenario.volume_factor != 1.0:
        options = SimulationOptions(days=days, seed=seed, volume_factor=scenario.volume_factor)
    base = run_replications(hospital, None, options, replications, workers)
    soft = run_replications(hospital, software, options, replications, workers, scenario=scenario)
    findings, unused = static_analysis(hospital, software)
    return SimulationReport(
        hospital_id=hospital.id,
        software_name=software.name,
        days=days,
        replications=replications,
        seed=seed,
        kpis=compare(base, soft),
        frictions=summarise_frictions(soft, hospital),
        static_findings=findings,
        unused_touchpoints=unused,
        scenario=scenario.name if scenario is not None else None,
        human=summarise_human(soft, scenario) if scenario is not None else None,
    )
