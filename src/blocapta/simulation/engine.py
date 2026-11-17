"""Moteur de simulation à événements discrets (SimPy) du jumeau numérique.

Une réplication simule ``days`` jours d'activité :
- les patients arrivent selon chaque parcours (loi journalière + profil horaire) ;
- chaque étape mobilise des ressources (personnel, salles…) soumises à leurs horaires ;
- à la fin d'une étape, des tâches de documentation sont réalisées par un rôle.

Si un logiciel est fourni, ses points de contact remplacent le système actuel pour
les tâches concernées et chaque écart entre la réalité simulée et ses contraintes
produit un ``FrictionEvent`` (cardinalité, couverture, interopérabilité, ressource,
disponibilité, charge).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import simpy

from ..models.hospital import Hospital, TimeWindow, hhmm_to_minutes
from ..models.results import FrictionEvent
from ..models.software import SoftwareModel

DAY = 1440
WEEK = 7 * DAY
DRAIN_DAYS = 2  # jours supplémentaires pour terminer les patients en cours

KPI_DEFS: dict[str, tuple[str, str]] = {
    "patients_termines": ("Patients pris en charge (parcours terminés)", "patients"),
    "duree_parcours_moy_min": ("Durée moyenne de parcours", "min"),
    "attente_ressources_moy_min": ("Attente moyenne de ressources par étape", "min"),
    "temps_documentation_h": ("Temps total consacré à la documentation", "h"),
    "temps_documentation_moy_min": ("Temps moyen par tâche de documentation", "min"),
    "saisies_total": ("Nombre total de saisies", "saisies"),
    "attente_poste_moy_min": ("Attente moyenne d'un poste informatique", "min"),
    "depassement_horaire_min_jour": ("Dépassement horaire moyen par jour et par service", "min"),
    "elements_a_risque": ("Éléments potentiellement non documentés", "éléments"),
    "pic_utilisateurs_simultanes": ("Pic d'utilisateurs simultanés du logiciel", "utilisateurs"),
    "jours_actifs": ("Jours d'activité simulés", "jours"),
}
KPI_PREFIX_DEFS: dict[str, tuple[str, str]] = {
    "temps_documentation_h.": ("Temps de documentation – {}", "h"),
    "utilisation.": ("Taux d'occupation – {}", "%"),
    "duree_parcours_moy_min.": ("Durée moyenne de parcours – {}", "min"),
    "patients_par_jour.": ("Patients par jour actif – {}", "patients/j"),
}


def kpi_label(key: str) -> tuple[str, str]:
    if key in KPI_DEFS:
        return KPI_DEFS[key]
    for prefix, (label, unit) in KPI_PREFIX_DEFS.items():
        if key.startswith(prefix):
            return label.format(key[len(prefix) :]), unit
    return key, ""


@dataclass
class SimulationOptions:
    days: int = 20
    seed: int = 42
    walk_to_fixed_workstation_min: float = 4.0
    overload_slowdown: float = 1.5
    workstation_wait_threshold_min: float = 2.0


@dataclass
class ReplicationResult:
    kpis: dict[str, float]
    frictions: list[FrictionEvent]
    task_counts: dict[str, int] = field(default_factory=dict)


def task_key(pathway: str, step: str, role: str, kind: str) -> str:
    return f"{pathway}|{step}|{role}|{kind}"


def off_periods(window: TimeWindow, horizon: float, resolution: int = 5) -> list[tuple[float, float]]:
    """Intervalles [début, fin) pendant lesquels une plage horaire est fermée."""
    periods: list[tuple[float, float]] = []
    start = None
    t = 0
    while t < horizon:
        closed = not window.contains(t % WEEK)
        if closed and start is None:
            start = t
        elif not closed and start is not None:
            periods.append((start, t))
            start = None
        t += resolution
    if start is not None:
        periods.append((start, horizon))
    return periods


def software_gaps(hospital: Hospital, software: SoftwareModel, system_id: str) -> tuple[bool, list[str]]:
    """(double saisie nécessaire dans le système actuel ?, catégories aval non couvertes)."""
    apps = hospital.information_system.applications
    covered = {i.target_category.lower() for i in software.interfaces if i.direction != "entrant"}
    category = apps[system_id].category.lower()
    downstream = sorted(
        {apps[i.target].category for i in hospital.information_system.interfaces if i.source == system_id}
    )
    return category not in covered, [c for c in downstream if c.lower() not in covered]


class Simulation:
    def __init__(
        self,
        hospital: Hospital,
        software: SoftwareModel | None = None,
        options: SimulationOptions | None = None,
        replication: int = 0,
    ):
        self.h = hospital
        self.sw = software
        self.o = options or SimulationOptions()
        ss = np.random.SeedSequence([self.o.seed, replication])
        a, d, k = ss.spawn(3)  # flux aléatoires séparés → nombres aléatoires communs entre scénarios
        self.rng_arr = np.random.default_rng(a)
        self.rng_dur = np.random.default_rng(d)
        self.rng_doc = np.random.default_rng(k)
        self.env = simpy.Environment()
        self.horizon = self.o.days * DAY
        self.run_until = self.horizon + DRAIN_DAYS * DAY
        self.pools = {
            n: simpy.PriorityResource(self.env, capacity=p.count) for n, p in hospital.resources.items() if p.count > 0
        }
        self.touchpoints = {tp.task_kind: tp for tp in software.touchpoints} if software else {}
        self._gaps: dict[str, tuple[bool, list[str]]] = {}
        # mesures
        self.busy: dict[str, float] = defaultdict(float)
        self.frictions: list[FrictionEvent] = []
        self.task_counts: dict[str, int] = defaultdict(int)
        self.lead_times: dict[str, list[float]] = defaultdict(list)
        self.step_waits: list[float] = []
        self.ws_waits: list[float] = []
        self.doc_times: dict[str, float] = defaultdict(float)
        self.doc_durations: list[float] = []
        self.entries = 0
        self.items_at_risk = 0
        self.current_users = 0
        self.peak_users = 0
        self.service_day_end: dict[tuple[str, int], float] = {}
        self.active_days: set[int] = set()

    # ------------------------------------------------------------------ run
    def run(self) -> ReplicationResult:
        for name, pool in self.h.resources.items():
            if pool.shift and pool.count > 0:
                self.env.process(self._shift_blocker(name, pool.count, pool.shift))
        for pw in self.h.pathways:
            self.env.process(self._arrivals(pw))
        self.env.run(until=self.run_until)
        return ReplicationResult(kpis=self._kpis(), frictions=self.frictions, task_counts=dict(self.task_counts))

    # -------------------------------------------------------- shift blocker
    def _shift_blocker(self, name: str, count: int, shift: TimeWindow):
        """Hors horaires, des « jetons » prioritaires occupent toutes les unités du pool.

        Une personne en cours de tâche termine d'abord (pas de préemption) : cela crée
        naturellement du dépassement horaire.
        """
        pool = self.pools[name]
        for start, end in off_periods(shift, self.run_until):
            if start > self.env.now:
                yield self.env.timeout(start - self.env.now)
            reqs = [pool.request(priority=-1) for _ in range(count)]
            yield self.env.all_of(reqs)
            if end > self.env.now:
                yield self.env.timeout(end - self.env.now)
            for r in reqs:
                pool.release(r)

    # ------------------------------------------------------------ arrivals
    def _arrival_times(self, pw) -> list[float]:
        w = pw.arrivals.window
        start, end = w.start_min, w.end_min
        if end <= start:
            end += DAY
        times: list[float] = []
        for day in range(self.o.days):
            if (day % 7) not in w.weekdays:
                continue
            n = int(round(pw.arrivals.per_day.sample(self.rng_arr)))
            if n <= 0:
                continue
            if pw.arrivals.hourly_profile:
                weights = np.array(
                    [
                        pw.arrivals.hourly_profile[h % 24] if start <= h * 60 + 59 and h * 60 < end else 0.0
                        for h in range(48)
                    ]
                )
                if weights.sum() == 0:
                    weights = None
            else:
                weights = None
            for _ in range(n):
                if weights is not None:
                    h = int(self.rng_arr.choice(48, p=weights / weights.sum()))
                    m = float(np.clip(h * 60 + self.rng_arr.uniform(0, 60), start, end - 1e-6))
                else:
                    m = float(self.rng_arr.uniform(start, end))
                times.append(day * DAY + m)
        return sorted(times)

    def _arrivals(self, pw):
        for i, t in enumerate(self._arrival_times(pw)):
            if t > self.env.now:
                yield self.env.timeout(t - self.env.now)
            self.active_days.add(int(t // DAY))
            self.env.process(self._patient(pw, i))

    # ------------------------------------------------------------- patient
    def _acquire(self, name: str):
        req = self.pools[name].request(priority=1)
        yield req
        return req

    def _release(self, name: str, req, since: float):
        self.pools[name].release(req)
        self.busy[name] += self.env.now - since

    def _patient(self, pw, pid: int):
        t0 = self.env.now
        for step in pw.steps:
            tw = self.env.now
            held: list[tuple[str, object, float]] = []
            for rname in sorted(step.resources):
                for _ in range(step.resources[rname]):
                    req = yield from self._acquire(rname)
                    held.append((rname, req, self.env.now))
            self.step_waits.append(self.env.now - tw)
            yield self.env.timeout(step.duration_min.sample(self.rng_dur))

            doc_roles = {d.role for d in step.documentation}
            kept: dict[str, tuple[object, float]] = {}
            for rname, req, since in held:
                if rname in doc_roles and rname not in kept:
                    kept[rname] = (req, since)  # le rôle documente avant d'être libéré
                else:
                    self._release(rname, req, since)
            for task in step.documentation:
                yield from self._document(pw, step, task, kept)
            for rname, (req, since) in kept.items():
                self._release(rname, req, since)
            self._mark_service_end(pw.service)
        self.lead_times[pw.id].append(self.env.now - t0)

    def _mark_service_end(self, service: str):
        day = int(self.env.now // DAY)
        key = (service, day)
        self.service_day_end[key] = max(self.service_day_end.get(key, 0.0), self.env.now)

    # -------------------------------------------------------- documentation
    def _friction(self, kind, pw, step, task, time_lost=0.0, items=0, detail=""):
        self.frictions.append(
            FrictionEvent(
                type=kind,
                pathway=pw.id,
                step=step.id,
                role=task.role,
                task_kind=task.kind,
                time_lost_min=round(float(time_lost), 3),
                items_at_risk=int(items),
                t=round(self.env.now, 2),
                detail=detail,
            )
        )

    def _gap(self, system_id: str) -> tuple[bool, list[str]]:
        if system_id not in self._gaps:
            self._gaps[system_id] = software_gaps(self.h, self.sw, system_id)
        return self._gaps[system_id]

    def _document(self, pw, step, task, kept):
        rng = self.rng_doc
        self.task_counts[task_key(pw.id, step.id, task.role, task.kind)] += 1
        n = max(1, int(round(task.items.sample(rng))))
        current_time = task.time_per_entry_min.sample(rng) + sum(task.time_per_item_min.sample(rng) for _ in range(n))
        tp = self.touchpoints.get(task.kind)
        use_sw = tp is not None and tp.replaces_current
        ws_pool = task.workstation
        entries = 1

        if not use_sw:
            duration = current_time
        elif tp.roles and task.role not in tp.roles:
            duration = current_time
            sw_time = tp.time_per_entry_min.sample(rng) + n * tp.time_per_item_min.mean_value()
            self._friction(
                "couverture", pw, step, task, time_lost=sw_time,
                detail=f"Rôle '{task.role}' non pris en charge : retranscription par un tiers ({n} élément(s))",
            )
            use_sw = False
        else:
            entries = math.ceil(n / tp.max_items_per_entry) if tp.max_items_per_entry else 1
            entry_times = [tp.time_per_entry_min.sample(rng) for _ in range(entries)]
            duration = sum(entry_times) + sum(tp.time_per_item_min.sample(rng) for _ in range(n))
            if entries > 1:
                risk = int(rng.binomial(entries - 1, tp.omission_risk_per_extra_entry))
                self._friction(
                    "cardinalite", pw, step, task, time_lost=sum(entry_times[1:]), items=risk,
                    detail=f"{n} éléments à documenter, {entries} saisies (max {tp.max_items_per_entry} par saisie)",
                )
            double, _ = self._gap(task.current_system)
            if double:
                duration += current_time
                self._friction(
                    "interoperabilite", pw, step, task, time_lost=current_time,
                    detail=f"Aucun flux vers '{task.current_system}' : double saisie",
                )
            if tp.requires_fixed_workstation and (ws_pool is None or self.h.resources[ws_pool].mobile):
                walk = self.o.walk_to_fixed_workstation_min
                duration += walk
                ws_pool = None
                self._friction(
                    "ressource", pw, step, task, time_lost=walk,
                    detail="Poste fixe requis mais aucun poste fixe sur le lieu de la tâche",
                )
            if self.sw.availability and not self.sw.availability.contains(self.env.now % WEEK):
                self._friction(
                    "disponibilite", pw, step, task, time_lost=entry_times[0], items=n,
                    detail=f"Logiciel indisponible à {_clock(self.env.now)} : saisie différée",
                )

        role_req = None
        if task.role not in kept:
            t_role = self.env.now
            role_req = yield from self._acquire(task.role)
            role_since = self.env.now
            self.step_waits.append(self.env.now - t_role)

        ws_req = None
        if ws_pool:
            tw = self.env.now
            ws_req = yield from self._acquire(ws_pool)
            ws_since = self.env.now
            wait = self.env.now - tw
            self.ws_waits.append(wait)
            if use_sw and wait > self.o.workstation_wait_threshold_min:
                self._friction(
                    "ressource", pw, step, task, time_lost=wait,
                    detail=f"Attente de {wait:.1f} min d'un poste '{ws_pool}'",
                )

        if use_sw:
            self.current_users += 1
            self.peak_users = max(self.peak_users, self.current_users)
            limit = self.sw.max_concurrent_users
            if limit and self.current_users > limit:
                slowed = duration * self.o.overload_slowdown
                self._friction(
                    "charge", pw, step, task, time_lost=slowed - duration,
                    detail=f"{self.current_users} utilisateurs simultanés pour une limite de {limit}",
                )
                duration = slowed

        yield self.env.timeout(duration)

        if use_sw:
            self.current_users -= 1
        if ws_req is not None:
            self._release(ws_pool, ws_req, ws_since)
        if role_req is not None:
            self._release(task.role, role_req, role_since)
        self.entries += entries
        self.doc_times[task.role] += duration
        self.doc_durations.append(duration)

    # ---------------------------------------------------------------- KPIs
    def _kpis(self) -> dict[str, float]:
        k: dict[str, float] = {}
        all_leads = [x for v in self.lead_times.values() for x in v]
        n_days = max(1, len(self.active_days))
        k["patients_termines"] = float(len(all_leads))
        k["duree_parcours_moy_min"] = float(np.mean(all_leads)) if all_leads else 0.0
        for pw in self.h.pathways:
            leads = self.lead_times.get(pw.id, [])
            k[f"duree_parcours_moy_min.{pw.id}"] = float(np.mean(leads)) if leads else 0.0
            k[f"patients_par_jour.{pw.id}"] = len(leads) / n_days
        k["attente_ressources_moy_min"] = float(np.mean(self.step_waits)) if self.step_waits else 0.0
        k["temps_documentation_h"] = sum(self.doc_times.values()) / 60
        for role, minutes in self.doc_times.items():
            k[f"temps_documentation_h.{role}"] = minutes / 60
        k["temps_documentation_moy_min"] = float(np.mean(self.doc_durations)) if self.doc_durations else 0.0
        k["saisies_total"] = float(self.entries)
        k["attente_poste_moy_min"] = float(np.mean(self.ws_waits)) if self.ws_waits else 0.0
        k["elements_a_risque"] = float(sum(f.items_at_risk for f in self.frictions if f.type == "cardinalite"))
        k["pic_utilisateurs_simultanes"] = float(self.peak_users)
        k["jours_actifs"] = float(n_days)

        overtimes = []
        for (service, day), end in self.service_day_end.items():
            closing = self.h.services[service].closing_time
            if closing:
                overtimes.append(max(0.0, end - (day * DAY + hhmm_to_minutes(closing))))
        k["depassement_horaire_min_jour"] = float(np.mean(overtimes)) if overtimes else 0.0

        for name, pool in self.h.resources.items():
            if pool.count <= 0:
                continue
            available = self.run_until
            if pool.shift:
                available -= sum(e - s for s, e in off_periods(pool.shift, self.run_until))
            capacity = pool.count * max(available, 1)
            k[f"utilisation.{name}"] = 100 * self.busy.get(name, 0.0) / capacity
        return {key: round(v, 4) for key, v in k.items()}


def _clock(t: float) -> str:
    m = int(t % DAY)
    return f"{m // 60:02d}:{m % 60:02d}"
