"""Lois de probabilité déclaratives, utilisées partout dans la configuration.

Convention : toutes les durées sont exprimées en MINUTES.
Chaque loi est sérialisable en YAML, par exemple ``{dist: lognormal, mean: 95, sd: 30}``.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator


class _Dist(BaseModel):
    model_config = {"extra": "forbid"}

    def sample(self, rng: np.random.Generator) -> float:  # pragma: no cover - interface
        raise NotImplementedError

    def mean_value(self) -> float:  # pragma: no cover - interface
        raise NotImplementedError


class Fixed(_Dist):
    dist: Literal["fixed"] = "fixed"
    value: float = Field(ge=0)

    def sample(self, rng):
        return float(self.value)

    def mean_value(self):
        return float(self.value)


class Exponential(_Dist):
    dist: Literal["exponential"] = "exponential"
    mean: float = Field(gt=0)

    def sample(self, rng):
        return float(rng.exponential(self.mean))

    def mean_value(self):
        return self.mean


class Normal(_Dist):
    """Loi normale tronquée à ``min`` (0 par défaut) pour éviter les durées négatives."""

    dist: Literal["normal"] = "normal"
    mean: float
    sd: float = Field(ge=0)
    min: float = 0.0

    def sample(self, rng):
        return float(max(self.min, rng.normal(self.mean, self.sd)))

    def mean_value(self):
        return max(self.min, self.mean)


class LogNormal(_Dist):
    """Paramétrée par la moyenne et l'écart-type de la variable elle-même (plus lisible pour un DSI)."""

    dist: Literal["lognormal"] = "lognormal"
    mean: float = Field(gt=0)
    sd: float = Field(gt=0)

    def _params(self) -> tuple[float, float]:
        sigma2 = math.log(1 + (self.sd / self.mean) ** 2)
        mu = math.log(self.mean) - sigma2 / 2
        return mu, math.sqrt(sigma2)

    def sample(self, rng):
        mu, sigma = self._params()
        return float(rng.lognormal(mu, sigma))

    def mean_value(self):
        return self.mean


class Gamma(_Dist):
    dist: Literal["gamma"] = "gamma"
    shape: float = Field(gt=0)
    scale: float = Field(gt=0)

    def sample(self, rng):
        return float(rng.gamma(self.shape, self.scale))

    def mean_value(self):
        return self.shape * self.scale


class Triangular(_Dist):
    dist: Literal["triangular"] = "triangular"
    low: float = Field(ge=0)
    mode: float
    high: float

    @model_validator(mode="after")
    def _check(self):
        if not (self.low <= self.mode <= self.high):
            raise ValueError("triangular : il faut low <= mode <= high")
        return self

    def sample(self, rng):
        if self.low == self.high:
            return float(self.low)
        return float(rng.triangular(self.low, self.mode, self.high))

    def mean_value(self):
        return (self.low + self.mode + self.high) / 3


class Uniform(_Dist):
    dist: Literal["uniform"] = "uniform"
    low: float = Field(ge=0)
    high: float

    def sample(self, rng):
        return float(rng.uniform(self.low, self.high))

    def mean_value(self):
        return (self.low + self.high) / 2


class Poisson(_Dist):
    """Loi de comptage (ex. nombre d'interventions par jour)."""

    dist: Literal["poisson"] = "poisson"
    lam: float = Field(ge=0)

    def sample(self, rng):
        return float(rng.poisson(self.lam))

    def mean_value(self):
        return self.lam


class Empirical(_Dist):
    """Loi discrète empirique : ``{valeur: probabilité}``. Ex. nombre d'actes CCAM par intervention."""

    dist: Literal["empirical"] = "empirical"
    values: dict[float, float]

    @field_validator("values")
    @classmethod
    def _normalise(cls, v: dict[float, float]) -> dict[float, float]:
        if not v:
            raise ValueError("empirical : au moins une valeur est requise")
        if any(p < 0 for p in v.values()):
            raise ValueError("empirical : probabilités négatives interdites")
        total = sum(v.values())
        if total <= 0:
            raise ValueError("empirical : la somme des probabilités doit être > 0")
        return {float(k): p / total for k, p in v.items()}

    def sample(self, rng):
        keys = list(self.values.keys())
        probs = list(self.values.values())
        return float(rng.choice(keys, p=probs))

    def mean_value(self):
        return sum(k * p for k, p in self.values.items())


class Quantiles(_Dist):
    """Fonction de répartition inverse linéaire par morceaux : ``{probabilité: valeur}``.

    Idéal pour reproduire des centiles observés (p05, p25, médiane, p75, p95…) sans
    imposer une forme paramétrique.
    """

    dist: Literal["quantiles"] = "quantiles"
    points: dict[float, float]

    @field_validator("points")
    @classmethod
    def _check(cls, v: dict[float, float]) -> dict[float, float]:
        pts = sorted((float(p), float(x)) for p, x in v.items())
        if len(pts) < 2 or pts[0][0] != 0.0 or pts[-1][0] != 1.0:
            raise ValueError("quantiles : il faut au moins les probabilités 0 et 1")
        if any(b[1] < a[1] for a, b in zip(pts, pts[1:], strict=False)):
            raise ValueError("quantiles : les valeurs doivent être croissantes")
        return dict(pts)

    def sample(self, rng):
        return float(np.interp(rng.random(), list(self.points.keys()), list(self.points.values())))

    def mean_value(self):
        ps, xs = list(self.points.keys()), list(self.points.values())
        return float(sum((ps[i + 1] - ps[i]) * (xs[i] + xs[i + 1]) / 2 for i in range(len(ps) - 1)))


class Samples(_Dist):
    """Rééchantillonnage direct d'observations réelles (bootstrap)."""

    dist: Literal["samples"] = "samples"
    samples: list[float] = Field(min_length=1)

    def sample(self, rng):
        return float(rng.choice(self.samples))

    def mean_value(self):
        return float(np.mean(self.samples))


Distribution = Annotated[
    Fixed | Exponential | Normal | LogNormal | Gamma | Triangular | Uniform | Poisson | Empirical | Quantiles | Samples,
    Field(discriminator="dist"),
]
