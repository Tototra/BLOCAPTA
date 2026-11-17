"""Ajustement automatique de lois de probabilité sur des durées observées."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from ..models.distributions import Empirical, Exponential, Fixed, Gamma, LogNormal, Normal, Poisson, Samples


@dataclass
class FitResult:
    distribution: object
    name: str
    aic: float | None
    ks_pvalue: float | None
    n: int


def _clean(samples) -> np.ndarray:
    x = np.asarray(samples, dtype=float)
    x = x[np.isfinite(x)]
    return x[x > 0]


def fit_duration(samples, min_samples: int = 15) -> FitResult:
    """Choisit la meilleure loi (AIC) parmi lognormale, gamma, exponentielle, normale.

    - moins de 3 observations : valeur fixe (médiane)
    - moins de ``min_samples`` : rééchantillonnage des observations (bootstrap)
    """
    x = _clean(samples)
    n = len(x)
    if n == 0:
        raise ValueError("Aucune durée positive à ajuster")
    if n < 3 or np.allclose(x, x[0]):
        return FitResult(Fixed(value=round(float(np.median(x)), 3)), "fixed", None, None, n)
    if n < min_samples:
        return FitResult(Samples(samples=[round(float(v), 3) for v in x]), "samples", None, None, n)

    candidates = []
    # lognormale
    shape, _, scale = stats.lognorm.fit(x, floc=0)
    ll = np.sum(stats.lognorm.logpdf(x, shape, 0, scale))
    dist_ln = stats.lognorm(shape, 0, scale)
    candidates.append(("lognormal", 2, ll, dist_ln, LogNormal(mean=float(dist_ln.mean()), sd=float(dist_ln.std()))))
    # gamma
    a, _, sc = stats.gamma.fit(x, floc=0)
    ll = np.sum(stats.gamma.logpdf(x, a, 0, sc))
    candidates.append(("gamma", 2, ll, stats.gamma(a, 0, sc), Gamma(shape=float(a), scale=float(sc))))
    # exponentielle
    _, sc = stats.expon.fit(x, floc=0)
    ll = np.sum(stats.expon.logpdf(x, 0, sc))
    candidates.append(("exponential", 1, ll, stats.expon(0, sc), Exponential(mean=float(sc))))
    # normale
    mu, sd = stats.norm.fit(x)
    ll = np.sum(stats.norm.logpdf(x, mu, sd))
    candidates.append(("normal", 2, ll, stats.norm(mu, sd), Normal(mean=float(mu), sd=float(sd))))

    best = None
    for name, k, ll, frozen, model in candidates:
        if not np.isfinite(ll):
            continue
        aic = 2 * k - 2 * ll
        if best is None or aic < best[1]:
            best = (name, aic, frozen, model)
    name, aic, frozen, model = best
    pval = float(stats.kstest(x, frozen.cdf).pvalue)
    return FitResult(model, name, float(aic), pval, n)


def fit_count(counts) -> object:
    """Loi de comptage journalière : Poisson si variance ≈ moyenne, sinon empirique."""
    c = np.asarray(counts, dtype=float)
    if len(c) == 0:
        return Poisson(lam=0)
    mean, var = c.mean(), c.var()
    if len(c) < 10 or (mean > 0 and 0.6 <= var / mean <= 1.6):
        return Poisson(lam=round(float(mean), 3))
    values, freq = np.unique(c.astype(int), return_counts=True)
    return Empirical(values={float(v): float(f) for v, f in zip(values, freq, strict=True)})
