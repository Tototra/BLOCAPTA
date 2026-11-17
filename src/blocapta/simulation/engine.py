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

WEEKDAY_LABELS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

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
    "cas_programmes": ("Cas programmés", "cas"),
    "cas_annules": ("Cas annulés avant le bloc", "cas"),
    "cas_deprogrammes": ("Cas déprogrammés le jour même (règle de fin)", "cas"),
    "taux_annulation_pct": ("Taux d'annulation", "%"),
    "heure_premier_cas_min": ("Heure médiane d'entrée du premier cas (minutes depuis minuit)", "min"),
    "occupation_salles_pct": ("Taux d'occupation des salles (temps patient / temps d'ouverture)", "%"),
    "taux_debordement_pct": ("Cas programmés sortant de salle après la fermeture", "%"),
    "occupation_capacite_pct": ("Occupation rapportée à la capacité totale (toutes salles × vacation)", "%"),
    "controle_ubiquite": ("Contrôle d'ubiquité (doit rester à 0)", "violations"),
    "durees_negatives": ("Durées négatives tirées (doit rester à 0)", "cas"),
}
KPI_PREFIX_DEFS: dict[str, tuple[str, str]] = {
    "temps_documentation_h.": ("Temps de documentation – {}", "h"),
    "utilisation.": ("Taux d'occupation – {}", "%"),
    "duree_parcours_moy_min.": ("Durée moyenne de parcours – {}", "min"),
    "patients_par_jour.": ("Patients par jour actif – {}", "patients/j"),
    "interventions_par_jour.": ("Interventions réalisées par {}", "cas/j"),
    "duree_mediane_cas_min.": ("Durée médiane d'occupation de salle – {}", "min"),
    "confiance_moyenne.": ("Confiance moyenne dans l'outil – {}", "0-1"),
    "taux_utilisation_outil.": ("Taux d'utilisation effective de l'outil – {}", "%"),
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
    volume_factor: float = 1.0  # ex. 0.55 pour simuler le mois d'août


@dataclass
class ReplicationResult:
    kpis: dict[str, float]
    frictions: list[FrictionEvent]
    task_counts: dict[str, int] = field(default_factory=dict)
    human: dict | None = None


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
    if category == "papier":  # remplacer un support papier ne demande aucune interface
        return False, []
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
        scenario=None,
    ):
        self.h = hospital
        self.sw = software
        self.o = options or SimulationOptions()
        if scenario is not None and scenario.volume_factor != 1.0:
            self.o = SimulationOptions(**{**self.o.__dict__, "volume_factor": scenario.volume_factor})
        ss = np.random.SeedSequence([self.o.seed, replication])
        # flux aléatoires séparés → nombres aléatoires communs (CRN) entre scénarios
        a, d, k, r, c, h = ss.spawn(6)
        self.rng_arr = np.random.default_rng(a)
        self.rng_dur = np.random.default_rng(d)
        self.rng_doc = np.random.default_rng(k)
        self.rng_res = np.random.default_rng(r)  # ouverture des salles, équipements optionnels
        self.rng_canc = np.random.default_rng(c)
        self.rng_human = np.random.default_rng(h)
        self.env = simpy.Environment()
        self.horizon = self.o.days * DAY
        self.run_until = self.horizon + DRAIN_DAYS * DAY
        self.pools = {
            n: simpy.PriorityResource(self.env, capacity=p.count) for n, p in hospital.resources.items() if p.count > 0
        }
        self.available_minutes: dict[str, float] = {}
        self._release_events = {n: self.env.event() for n in self.pools}
        self.touchpoints = {tp.task_kind: tp for tp in software.touchpoints} if software else {}
        self._gaps: dict[str, tuple[bool, list[str]]] = {}
        # mesures
        self.busy: dict[str, float] = defaultdict(float)
        self.frictions: list[FrictionEvent] = []
        self.task_counts: dict[str, int] = defaultdict(int)
        self.lead_times: dict[str, list[float]] = defaultdict(list)
        self.case_durations: dict[str, list[float]] = defaultdict(list)
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
        self.scheduled = 0
        self.cancelled = 0
        self.completed_by_weekday: dict[int, int] = defaultdict(int)
        self.first_start_by_day: dict[int, float] = {}
        self.negative_durations = 0
        self.room_patient_minutes = 0.0
        self.room_minutes_weekdays = 0.0
        self.deprogrammed = 0
        self.room_exits = 0
        self.room_overflows = 0
        self.ubiquity_violations = 0
        self.human = None
        if scenario is not None and software is not None:
            from .human import HumanLayer

            self.human = HumanLayer(scenario, software)

    # ------------------------------------------------------------------ run
    def run(self) -> ReplicationResult:
        ordered = sorted(self.h.resources.items(), key=lambda kv: any(s.follows for s in kv[1].shifts))
        for name, pool in ordered:
            if pool.count <= 0:
                continue
            timeline, available = self._availability_timeline(pool)
            self.available_minutes[name] = available
            if timeline:
                self.env.process(self._availability_blocker(name, timeline))
        for pw in self.h.pathways:
            if pw.arrivals.mode == "poisson":
                self.env.process(self._arrivals(pw))
        if self.h.programme is not None:
            self.env.process(self._planned_arrivals())
        if self.human is not None:
            self.human.start(self)
        self.env.run(until=self.run_until)
        result = ReplicationResult(kpis=self._kpis(), frictions=self.frictions, task_counts=dict(self.task_counts))
        if self.human is not None:
            result.human = self.human.summary()
            result.kpis.update(self.human.kpis())
        return result

    # ------------------------------------------------- disponibilité des ressources
    def _availability_timeline(self, pool, resolution: int = 5) -> tuple[list[tuple[float, int]], float]:
        """Nombre d'unités INDISPONIBLES au cours du temps (équipes, ouverture des salles).

        Renvoie les changements (t, n) et le total de minutes-unités disponibles.
        """
        groups = pool.shift_groups()
        always = len(groups) == 1 and groups[0][0] is None and groups[0][2] is None
        if always:
            return [], float(pool.count * self.run_until)
        n_days = int(self.run_until // DAY) + 1
        opened = []  # opened[day][group]
        self._opened = getattr(self, "_opened", {})
        for _day in range(n_days):
            row = []
            for _, cnt, p in groups:
                row.append(int(self.rng_res.binomial(cnt, p)) if p is not None else cnt)
            opened.append(row)
        self._opened[id(pool)] = (groups, opened)
        followers = pool.followers()
        changes: list[tuple[float, int]] = []
        last = None
        available_total = 0.0
        t = 0
        while t < self.run_until:
            day = int(t // DAY)
            minute_of_week = t % WEEK
            avail = 0
            for gi, (window, cnt, _) in enumerate(groups):
                if window is None or window.contains(minute_of_week):
                    start_day = day
                    if window is not None and window.end_min <= window.start_min and (t % DAY) < window.end_min:
                        start_day = max(0, day - 1)  # plage de nuit commencée la veille
                    follower = followers.get(gi)
                    if follower is not None:
                        units = self._open_units(follower.follows, t)
                        avail += min(cnt, int(round(follower.per_unit * units)) + follower.extra)
                    else:
                        avail += opened[start_day][gi]
            avail = min(avail, pool.count)
            available_total += avail * resolution
            unavailable = pool.count - avail
            if unavailable != last:
                changes.append((float(t), unavailable))
                last = unavailable
            t += resolution
        return changes, available_total

    def _open_units(self, pool_name: str, t: float) -> int:
        """Unités ouvertes d'un pool à l'instant t (selon ses équipes et son tirage du jour)."""
        pool = self.h.resources[pool_name]
        entry = self._opened.get(id(pool))
        if entry is None:
            return pool.count
        groups, opened = entry
        day = int(t // DAY)
        total = 0
        for gi, (window, _, _) in enumerate(groups):
            if window is None or window.contains(t % WEEK):
                start_day = day
                if window is not None and window.end_min <= window.start_min and (t % DAY) < window.end_min:
                    start_day = max(0, day - 1)
                total += opened[start_day][gi]
        return min(total, pool.count)

    def _availability_blocker(self, name: str, timeline: list[tuple[float, int]]):
        """Des « jetons » prioritaires occupent les unités indisponibles.

        Une personne en cours de tâche termine d'abord (pas de préemption) : cela crée
        naturellement du dépassement horaire.
        """
        pool = self.pools[name]
        held: list = []
        for t, n in timeline:
            if t > self.env.now:
                yield self.env.timeout(t - self.env.now)
            while len(held) < n:
                held.append(pool.request(priority=-1))
            while len(held) > n:
                req = held.pop()
                if req.triggered:
                    pool.release(req)
                else:
                    req.cancel()
                self._notify(name)

    # ------------------------------------------------------------ arrivals
    def _arrival_times(self, pw) -> list[float]:
        w = pw.arrivals.window
        start, end = w.start_min, w.end_min
        if end <= start:
            end += DAY
        if pw.arrivals.hourly_profile:
            weights = np.array(
                [pw.arrivals.hourly_profile[h % 24] if start <= h * 60 + 59 and h * 60 < end else 0.0 for h in range(48)]
            )
            if weights.sum() == 0:
                weights = None
        else:
            weights = None
        times: list[float] = []
        for day in range(self.o.days):
            if (day % 7) not in w.weekdays:
                continue
            lam = pw.arrivals.per_day.sample(self.rng_arr)
            factor = pw.arrivals.weekday_factors[day % 7] if pw.arrivals.weekday_factors else 1.0
            mean = lam * factor * self.o.volume_factor
            n = int(self.rng_arr.poisson(mean)) if pw.arrivals.weekday_factors or self.o.volume_factor != 1 else int(round(mean))
            for _ in range(max(0, n)):
                if weights is not None:
                    h = int(self.rng_arr.choice(48, p=weights / weights.sum()))
                    m = float(np.clip(h * 60 + self.rng_arr.uniform(0, 60), start, end - 1e-6))
                else:
                    m = float(self.rng_arr.uniform(start, end))
                times.append(day * DAY + m)
        return sorted(times)

    def _plan(self) -> list[tuple[float, object, float, float]]:
        """Construit le programme opératoire : (arrivée, parcours, durée du cas, heure prévue d'entrée)."""
        prog = self.h.programme
        pool = self.h.resources[prog.room_pool]
        groups, opened = self._opened.get(id(pool), (pool.shift_groups(), None))
        by_id = {p.id: p for p in self.h.pathways}
        ids = list(prog.specialty_weights)
        weights = np.array([prog.specialty_weights[i] for i in ids], dtype=float)
        weights /= weights.sum()
        start, end = hhmm_to_minutes(prog.start), hhmm_to_minutes(prog.end)
        planned = []
        for day in range(self.o.days):
            wd = day % 7
            if wd not in prog.weekdays:
                continue
            t_start = wd * DAY + start
            if opened is not None:
                n_rooms = sum(
                    opened[day][gi]
                    for gi, (window, _, _) in enumerate(groups)
                    if window is None or window.contains(t_start)
                )
            else:
                n_rooms = pool.count
            n_rooms = int(round(n_rooms * self.o.volume_factor))
            limit = start + prog.fill_ratio * (end - start)
            for _room in range(n_rooms):
                pw = by_id[ids[int(self.rng_arr.choice(len(ids), p=weights))]]
                cursor = float(start)
                first = True
                while True:
                    # un cas est programmé s'il COMMENCE dans la vacation : pas de biais vers les cas courts
                    dur = max(1.0, pw.case_duration_min.sample(self.rng_arr))
                    if not first and cursor > limit:
                        break
                    planned.append((day * DAY + cursor - prog.call_ahead_min, pw, dur, day * DAY + cursor))
                    cursor += dur + prog.turnover_min
                    first = False
        return sorted(planned, key=lambda x: x[0])

    def _planned_arrivals(self):
        for i, (t, pw, dur, planned_start) in enumerate(self._plan()):
            if t > self.env.now:
                yield self.env.timeout(t - self.env.now)
            self.active_days.add(int(t // DAY))
            self.env.process(self._patient(pw, i, planned=(dur, planned_start)))

    def _arrivals(self, pw):
        for i, t in enumerate(self._arrival_times(pw)):
            if t > self.env.now:
                yield self.env.timeout(t - self.env.now)
            self.active_days.add(int(t // DAY))
            self.env.process(self._patient(pw, i))

    # ------------------------------------------------------------- patient
    def _acquire(self, name: str, priority: int = 1):
        pool = self.pools[name]
        req = pool.request(priority=priority)
        yield req
        if len(pool.users) > pool.capacity:  # garde-fou : une unité à deux endroits
            self.ubiquity_violations += 1
        return req

    def _release(self, name: str, req, since: float):
        self.pools[name].release(req)
        self.busy[name] += self.env.now - since
        self._notify(name)

    def _notify(self, name: str):
        ev = self._release_events[name]
        self._release_events[name] = self.env.event()
        if not ev.triggered:
            ev.succeed()

    def _free(self, name: str) -> int:
        pool = self.pools[name]
        return pool.capacity - len(pool.users) - len(pool.queue)

    def _acquire_all(self, needed: dict[str, int], priority: int = 1, deadline: float | None = None):
        """Acquisition atomique : on ne prend rien tant que tout n'est pas disponible.

        Évite les interblocages (attente circulaire) entre étapes qui partagent des ressources.
        Avec ``deadline``, renvoie None si les ressources ne sont pas obtenues à temps.
        """
        needed = {n: q for n, q in needed.items() if q > 0}
        if not needed:
            return []
        while True:
            if deadline is not None and self.env.now > deadline:
                return None
            if all(self._free(n) >= q for n, q in needed.items()):
                reqs = [(n, self.pools[n].request(priority=priority)) for n, q in needed.items() for _ in range(q)]
                yield self.env.all_of([r for _, r in reqs])
                for n in needed:
                    if len(self.pools[n].users) > self.pools[n].capacity:
                        self.ubiquity_violations += 1
                return [(n, r, self.env.now) for n, r in reqs]
            events = [self._release_events[n] for n in needed]
            if deadline is not None:
                events.append(self.env.timeout(max(0.0, deadline - self.env.now) + 1e-6))
            yield self.env.any_of(events)

    def _sample_duration(self, dist, rng) -> float:
        v = dist.sample(rng)
        if v < 0:
            self.negative_durations += 1
            v = 0.0
        return v

    def _patient(self, pw, pid: int, planned: tuple[float, float] | None = None):
        self.scheduled += 1
        if pw.arrivals.cancellation_rate and self.rng_canc.random() < pw.arrivals.cancellation_rate:
            self.cancelled += 1
            return
        t0 = self.env.now
        priority = 0 if pw.urgent else 1
        if planned is not None:
            case_total, not_before_abs = planned
        else:
            not_before_abs = None
            case_total = self._sample_duration(pw.case_duration_min, self.rng_dur) if pw.case_duration_min else None
        if case_total is not None:
            self.case_durations[pw.id].append(case_total)
        carried: dict[str, list[tuple[object, float]]] = defaultdict(list)
        for step in pw.steps:
            dur = (
                self._sample_duration(step.duration_min, self.rng_dur)
                if step.duration_min is not None
                else case_total * step.duration_share
            )
            needed = dict(step.resources)
            for rname, prob in step.optional_resources.items():
                if self.rng_res.random() < prob:
                    needed[rname] = needed.get(rname, 0) + 1

            if step.detached:
                given = {r: carried.pop(r) for r in list(carried) if r in needed}
                if any(self._is_room(r) for r in given):
                    self._room_exit(pw)
                self.env.process(self._detached(pw, step, needed, given, dur, priority))
                continue

            tw = self.env.now
            entering_room = step.duration_share and not any(self._is_room(r) for r in carried)
            if entering_room and (pw.room_not_before or not_before_abs is not None):
                opening = not_before_abs if not_before_abs is not None else (
                    (self.env.now // DAY) * DAY + hhmm_to_minutes(pw.room_not_before)
                )
                if self.env.now < opening:
                    yield self.env.timeout(opening - self.env.now)
                tw = self.env.now
            held: list[tuple[str, object, float]] = []
            missing: dict[str, int] = {}
            for rname in sorted(needed):
                have = carried.get(rname, [])
                for _ in range(needed[rname]):
                    if have:
                        req, since = have.pop(0)
                        held.append((rname, req, since))
                    else:
                        missing[rname] = missing.get(rname, 0) + 1
            deadline = None
            if pw.room_last_start and step.duration_share and not any(self._is_room(r) for r in carried):
                deadline = (self.env.now // DAY) * DAY + hhmm_to_minutes(pw.room_last_start)
            got = yield from self._acquire_all(missing, priority, deadline)
            if got is None:  # règle de fin : le cas programmé est déprogrammé
                for rname, req, since in held:
                    self._release(rname, req, since)
                for rname, lst in carried.items():
                    for req, since in lst:
                        self._release(rname, req, since)
                self.deprogrammed += 1
                return
            held += got
            for rname, lst in carried.items():  # ressources reçues mais non demandées : libérées
                for req, since in lst:
                    self._release(rname, req, since)
            carried = defaultdict(list)
            self.step_waits.append(self.env.now - tw)
            in_room = any(self._is_room(r) for r, _, _ in held)
            if in_room and step.duration_share and not pw.urgent:
                day = int(self.env.now // DAY)
                self.first_start_by_day.setdefault(day, self.env.now)
            yield self.env.timeout(dur)
            if in_room:
                self.room_patient_minutes += dur
                if int(self.env.now // DAY) % 7 < 5:
                    self.room_minutes_weekdays += dur

            doc_roles = {d.role for d in step.documentation}
            kept: dict[str, tuple[object, float]] = {}
            for rname, req, since in held:
                if rname in step.carry:
                    carried[rname].append((req, since))
                elif rname in doc_roles and rname not in kept:
                    kept[rname] = (req, since)  # le rôle documente avant d'être libéré
                else:
                    self._release(rname, req, since)
            if in_room and not any(self._is_room(r) for r in carried):
                self._room_exit(pw)
            for task in step.documentation:
                yield from self._document(pw, step, task, kept)
            for rname, (req, since) in kept.items():
                self._release(rname, req, since)
            self._mark_service_end(pw.service)
        for rname, lst in carried.items():
            for req, since in lst:
                self._release(rname, req, since)
        self.lead_times[pw.id].append(self.env.now - t0)
        self.completed_by_weekday[int(t0 // DAY) % 7] += 1

    def _detached(self, pw, step, needed, given, dur, priority):
        held = []
        missing: dict[str, int] = {}
        for rname in sorted(needed):
            have = given.get(rname, [])
            for _ in range(needed[rname]):
                if have:
                    req, since = have.pop(0)
                    held.append((rname, req, since))
                else:
                    missing[rname] = missing.get(rname, 0) + 1
        held += yield from self._acquire_all(missing, priority)
        for rname, lst in given.items():
            for req, since in lst:
                self._release(rname, req, since)
        yield self.env.timeout(dur)
        for rname, req, since in held:
            self._release(rname, req, since)
        self._mark_service_end(pw.service)

    def _is_room(self, name: str) -> bool:
        pool = self.h.resources.get(name)
        return pool is not None and pool.kind == "salle" and pool.service is not None and name.startswith("salle")

    def _room_exit(self, pw):
        """Sortie de salle : sert au taux de débordement (cas programmés finissant après la fermeture)."""
        if pw.urgent:
            return
        self.room_exits += 1
        closing = self.h.services[pw.service].closing_time
        if closing and (self.env.now % DAY) > hhmm_to_minutes(closing) and (int(self.env.now // DAY) % 7) < 5:
            self.room_overflows += 1

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

    def _role_supported(self, pool_name: str, roles: list[str]) -> bool:
        pool = self.h.resources.get(pool_name)
        names = {pool_name.lower()}
        if pool is not None and pool.role:
            names.add(pool.role.lower())
        return bool(names & {r.lower() for r in roles})

    def _gap(self, system_id: str) -> tuple[bool, list[str]]:
        if system_id not in self._gaps:
            self._gaps[system_id] = software_gaps(self.h, self.sw, system_id)
        return self._gaps[system_id]

    def _document(self, pw, step, task, kept):
        rng = self.rng_doc
        n = int(round(task.items.sample(rng)))
        if n <= 0:
            return  # rien à documenter pour ce cas
        self.task_counts[task_key(pw.id, step.id, task.role, task.kind)] += 1
        current_time = task.time_per_entry_min.sample(rng) + sum(task.time_per_item_min.sample(rng) for _ in range(n))
        tp = self.touchpoints.get(task.kind)
        use_sw = tp is not None and tp.replaces_current
        ws_pool = task.workstation
        entries = 1
        hl = self.human
        agent = None
        outcome = 1.0
        if use_sw and hl is not None and not hl.deployed(self.env.now):
            use_sw = False  # l'outil n'est pas encore déployé

        if not use_sw:
            duration = current_time
        elif tp.roles and not self._role_supported(task.role, tp.roles):
            duration = current_time
            sw_time = tp.time_per_entry_min.sample(rng) + n * tp.time_per_item_min.mean_value()
            self._friction(
                "couverture", pw, step, task, time_lost=sw_time,
                detail=f"Rôle '{task.role}' non pris en charge : retranscription par un tiers ({n} élément(s))",
            )
            use_sw = False
        else:
            if hl is not None and hl.cfg.enabled:
                agent = hl.pick(task.role)
            sw_estimate = tp.time_per_entry_min.mean_value() + n * tp.time_per_item_min.mean_value()
            if agent is not None and hl.bypasses(agent):
                duration = current_time
                self._friction(
                    "adoption", pw, step, task, time_lost=sw_estimate,
                    detail=f"Confiance faible ({agent.trust:.2f}) : outil contourné, retranscription ultérieure",
                )
                hl.record_use(agent, used_tool=False, duration=duration)
                agent = None
                use_sw = False
            elif hl is not None and hl.is_down(self.env.now):
                rel = self.sw.reliability
                reentry = sw_estimate if rel.reentry_after_outage else 0.0
                duration = current_time * rel.degraded_time_factor + reentry
                self._friction(
                    "panne", pw, step, task, time_lost=duration - current_time,
                    detail="Logiciel en panne : mode dégradé" + (" puis resaisie" if reentry else ""),
                )
                if agent is not None:
                    hl.update(agent, 0.0)
                    hl.record_use(agent, used_tool=True, duration=duration)
                agent = None
                use_sw = False
        if use_sw:
            entries = math.ceil(n / tp.max_items_per_entry) if tp.max_items_per_entry else 1
            entry_times = [tp.time_per_entry_min.sample(rng) for _ in range(entries)]
            duration = sum(entry_times) + sum(tp.time_per_item_min.sample(rng) for _ in range(n))
            if agent is not None:
                factor = hl.learning_factor(agent)
                if factor > 1.0001:
                    duration *= factor
            if entries > 1:
                risk = int(rng.binomial(entries - 1, tp.omission_risk_per_extra_entry))
                outcome = min(outcome, hl.cfg.partial_success_outcome) if hl is not None else outcome
                self._friction(
                    "cardinalite", pw, step, task, time_lost=sum(entry_times[1:]), items=risk,
                    detail=f"{n} éléments à documenter, {entries} saisies (max {tp.max_items_per_entry} par saisie)",
                )
            double, _ = self._gap(task.current_system)
            if double:
                duration += current_time
                outcome = min(outcome, hl.cfg.partial_success_outcome) if hl is not None else outcome
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
            if agent is not None:
                hl.update(agent, outcome)
                hl.record_use(agent, used_tool=True, duration=duration)
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
            available = self.available_minutes.get(name) or pool.count * self.run_until
            k[f"utilisation.{name}"] = 100 * self.busy.get(name, 0.0) / max(available, 1)

        # fidélité au bloc réel
        k["cas_programmes"] = float(self.scheduled)
        k["cas_annules"] = float(self.cancelled)
        k["taux_annulation_pct"] = 100 * self.cancelled / self.scheduled if self.scheduled else 0.0
        k["cas_deprogrammes"] = float(self.deprogrammed)
        for wd, label in enumerate(WEEKDAY_LABELS):
            n_wd = sum(1 for d in range(self.o.days) if d % 7 == wd)
            if n_wd:
                k[f"interventions_par_jour.{label}"] = self.completed_by_weekday.get(wd, 0) / n_wd
        for pw in self.h.pathways:
            durs = self.case_durations.get(pw.id)
            if durs:
                k[f"duree_mediane_cas_min.{pw.id}"] = float(np.median(durs))
        firsts = [t % DAY for d, t in self.first_start_by_day.items() if d % 7 < 5]
        if firsts:
            k["heure_premier_cas_min"] = float(np.median(firsts))
        rooms = [n for n in self.h.resources if self._is_room(n) and n in self.available_minutes]
        avail_rooms = sum(self.available_minutes[n] for n in rooms)
        if avail_rooms:
            k["occupation_salles_pct"] = 100 * self.room_patient_minutes / avail_rooms
        prog = self.h.programme
        if prog is not None:
            n_rooms = self.h.resources[prog.room_pool].count
            n_wd = sum(1 for d in range(self.o.days) if d % 7 in prog.weekdays)
            capacity = n_rooms * (hhmm_to_minutes(prog.end) - hhmm_to_minutes(prog.start)) * n_wd
            if capacity:
                k["occupation_capacite_pct"] = 100 * self.room_minutes_weekdays / capacity
        if self.room_exits:
            k["taux_debordement_pct"] = 100 * self.room_overflows / self.room_exits
        k["controle_ubiquite"] = float(self.ubiquity_violations)
        k["durees_negatives"] = float(self.negative_durations)
        return {key: round(v, 4) for key, v in k.items()}


def _clock(t: float) -> str:
    m = int(t % DAY)
    return f"{m // 60:02d}:{m % 60:02d}"
