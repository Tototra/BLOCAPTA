"""Couche facteur humain (MOBO) et fiabilité du logiciel, branchée sur le moteur.

Chaque soignant concerné par l'outil est un agent avec :
- une confiance T ∈ [0, 1] mise à jour à chaque usage (règle de Rescorla-Wagner avec
  aversion à la perte) :  δ = résultat − T ;  ΔT = α·δ si δ ≥ 0, α·λ·δ si δ < 0 ;
- une expérience (nombre d'usages) qui réduit le temps d'usage (courbe d'apprentissage) ;
- des liens pondérés vers ses collègues : chaque jour  ΔT_i = κ · Σ_j w_ij (T_j − T_i)
  avec w_ij proportionnel à l'autorité de j (gradient d'Edmondson), renforcé dans l'équipe.

Sous un seuil de confiance, un agent peut contourner l'outil (retour à l'ancien
processus) : c'est la friction « adoption ».
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..models.scenario import Scenario

DAY = 1440


@dataclass
class Agent:
    pool: str
    index: int
    role: str
    trust: float
    authority: float
    label: str = ""
    alpha: float | None = None
    uses: int = 0
    tool_uses: int = 0
    bypasses: int = 0
    history: list[float] = field(default_factory=list)


class HumanLayer:
    def __init__(self, scenario: Scenario, software):
        self.sc = scenario
        self.cfg = scenario.human
        self.sw = software
        self.agents: dict[str, list[Agent]] = {}
        self.outages: list[tuple[float, float]] = []  # (début, fin)
        self.outage_minutes = 0.0
        self.sw_durations_by_week: dict[int, list[float]] = defaultdict(list)
        self.sim = None

    # ---------------------------------------------------------------- mise en place
    def start(self, sim) -> None:
        self.sim = sim
        rng = sim.rng_human
        users = {t.role for p in sim.h.pathways for s in p.steps for t in s.documentation if t.kind in sim.touchpoints}
        team = {n for n, r in sim.h.resources.items() if r.kind == "humain" and (r.role or n) in self.cfg.team_roles}
        team -= {n for n in team if n.endswith("_supervision")}
        self.user_pools = users
        pools = sorted(users | team)
        for pool_name in pools:
            pool = sim.h.resources[pool_name]
            role = pool.role or pool_name
            base = self.cfg.initial_trust_by_role.get(pool_name, self.cfg.initial_trust_by_role.get(role, self.cfg.initial_trust))
            authority = self.cfg.authority_by_role.get(pool_name, self.cfg.authority_by_role.get(role, 1.0))
            self.agents[pool_name] = [
                Agent(pool=pool_name, index=i, role=role, trust=float(np.clip(base + rng.normal(0, 0.05), 0, 1)), authority=authority)
                for i in range(max(1, pool.count))
            ]
        for o in self.cfg.overrides:
            targets = self.agents.get(o.pool) or [a for lst in self.agents.values() for a in lst if a.role == o.pool]
            if not targets:
                continue
            a = targets[min(o.index, len(targets) - 1)]
            if o.initial_trust is not None:
                a.trust = o.initial_trust
            if o.authority is not None:
                a.authority = o.authority
            if o.alpha is not None:
                a.alpha = o.alpha
            a.label = o.label
        self._build_network()
        sim.env.process(self._daily())
        sim.env.process(self._outage_process())

    def _build_network(self) -> None:
        everyone = [a for lst in self.agents.values() for a in lst]
        self.everyone = everyone
        n = len(everyone)
        w = np.zeros((n, n))
        for i, ai in enumerate(everyone):
            for j, aj in enumerate(everyone):
                if i == j:
                    continue
                w[i, j] = aj.authority * (self.cfg.same_team_factor if ai.pool == aj.pool else 1.0)
            norm = np.abs(w[i]).sum()
            if norm:
                w[i] /= norm
        self.w = w

    # ---------------------------------------------------------------- dynamique
    def _daily(self):
        env = self.sim.env
        while env.now < self.sim.run_until:
            self._record_day()
            yield env.timeout(DAY - (env.now % DAY) if env.now % DAY else DAY)
            if self.cfg.kappa and len(self.everyone) > 1:
                t = np.array([a.trust for a in self.everyone])
                delta = self.cfg.kappa * (self.w @ t - self.w.sum(axis=1) * t)
                for a, d in zip(self.everyone, delta, strict=True):
                    a.trust = float(np.clip(a.trust + d, 0, 1))

    def _record_day(self) -> None:
        for a in self.everyone:
            a.history.append(a.trust)

    def _outage_process(self):
        env, rel, rng = self.sim.env, self.sw.reliability, self.sim.rng_human
        planned = sorted((i.start_min, i.duration_min) for i in self.sc.incidents)
        events = list(planned)
        if self.sc.random_outages and rel.availability_pct < 100:
            down = 1 - rel.availability_pct / 100
            mean_gap = rel.mean_outage_min / down - rel.mean_outage_min
            t = self.sc.deployment_min
            while t < self.sim.horizon:
                t += rng.exponential(mean_gap)
                events.append((t, rng.exponential(rel.mean_outage_min)))
        for start, dur in sorted(events):
            if start >= self.sim.run_until:
                break
            if start > env.now:
                yield env.timeout(start - env.now)
            supported = self.support_on_site(env.now)
            if supported:
                dur *= rel.support_outage_factor
            self.outages.append((env.now, env.now + dur))
            self.outage_minutes += dur
            # une panne est vécue par toute l'équipe présente (aversion à la perte)
            if self.cfg.enabled:
                outcome = self.cfg.support_outage_outcome if supported else self.cfg.outage_team_outcome
                for pool_name, agents in self.agents.items():
                    present = self.sim._open_units(pool_name, env.now) if pool_name in self.sim.pools else len(agents)
                    o = outcome if pool_name in self.user_pools else max(outcome, self.cfg.non_user_outage_outcome)
                    for a in agents[: max(0, present)]:
                        self.update(a, o)

    # ---------------------------------------------------------------- requêtes du moteur
    def deployed(self, t: float) -> bool:
        return t >= self.sc.deployment_min

    def support_on_site(self, t: float) -> bool:
        return t < self.sc.deployment_min + self.sc.support_on_site_days * DAY

    def is_down(self, t: float) -> bool:
        return any(s <= t < e for s, e in self.outages)

    def pick(self, pool: str) -> Agent | None:
        lst = self.agents.get(pool)
        if not lst:
            return None
        return lst[int(self.sim.rng_human.integers(len(lst)))]

    def bypasses(self, agent: Agent) -> bool:
        thr = self.cfg.bypass_threshold
        if agent.trust >= thr or thr == 0:
            return False
        return self.sim.rng_human.random() < (thr - agent.trust) / thr

    def learning_factor(self, agent: Agent) -> float:
        extra = self.cfg.learning_initial_factor - 1
        return 1 + extra * 0.5 ** (agent.tool_uses / self.cfg.learning_half_uses)

    def update(self, agent: Agent, outcome: float) -> None:
        delta = outcome - agent.trust
        alpha = agent.alpha if agent.alpha is not None else self.cfg.alpha
        gain = alpha * delta if delta >= 0 else alpha * self.cfg.loss_aversion * delta
        agent.trust = float(np.clip(agent.trust + gain, 0, 1))

    def record_use(self, agent: Agent, used_tool: bool, duration: float) -> None:
        agent.uses += 1
        if used_tool:
            agent.tool_uses += 1
            self.sw_durations_by_week[int(self.sim.env.now // (7 * DAY))].append(duration)
        else:
            agent.bypasses += 1

    # ---------------------------------------------------------------- résultats
    def by_role(self) -> dict[str, list[Agent]]:
        out: dict[str, list[Agent]] = defaultdict(list)
        for a in self.everyone:
            out[a.pool].append(a)
        return out

    def kpis(self) -> dict[str, float]:
        k: dict[str, float] = {}
        for pool, agents in self.by_role().items():
            k[f"confiance_moyenne.{pool}"] = round(float(np.mean([a.trust for a in agents if not a.label] or [a.trust for a in agents])), 4)
            uses = sum(a.uses for a in agents)
            if uses:
                k[f"taux_utilisation_outil.{pool}"] = round(100 * sum(a.tool_uses for a in agents) / uses, 2)
        k["pannes"] = float(len(self.outages))
        k["minutes_de_panne"] = round(self.outage_minutes, 1)
        return k

    def summary(self) -> dict:
        days = int(self.sim.run_until // DAY)
        trust_by_day = {}
        for pool, agents in self.by_role().items():
            series = []
            for d in range(min(days, min(len(a.history) for a in agents))):
                series.append(round(float(np.mean([a.history[d] for a in agents])), 4))
            trust_by_day[pool] = series
        weeks = max(self.sw_durations_by_week) + 1 if self.sw_durations_by_week else 0
        families: dict[str, list[Agent]] = defaultdict(list)
        for a in self.everyone:
            families[a.role].append(a)
        trust_by_family = {}
        usage_by_family = {}
        for fam, agents in families.items():
            n = min(days, min(len(a.history) for a in agents))
            trust_by_family[fam] = [round(float(np.mean([a.history[d] for a in agents if not a.label] or [a.history[d] for a in agents])), 4) for d in range(n)]
            uses = sum(a.uses for a in agents)
            if uses and any(a.pool in self.user_pools for a in agents):
                usage_by_family[fam] = round(100 * sum(a.tool_uses for a in agents) / uses, 2)
        special = {
            f"{a.label} ({a.pool})": [round(x, 4) for x in a.history[:days]] for a in self.everyone if a.label
        }
        return {
            "trust_by_day": trust_by_day,
            "special_agents": special,
            "trust_by_family": trust_by_family,
            "usage_by_family": usage_by_family,
            "sw_minutes_by_week": [
                round(float(np.mean(self.sw_durations_by_week[w])), 3) if self.sw_durations_by_week.get(w) else 0.0
                for w in range(weeks)
            ],
            "outages": len(self.outages),
            "outage_minutes": round(self.outage_minutes, 1),
        }
