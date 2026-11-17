import numpy as np
import pandas as pd
import pytest

from blocapta.calibration import (
    ColumnMapping,
    build_pathway,
    fit_count,
    fit_duration,
    generate_bloc_log,
    normalise,
    variants,
)
from blocapta.models.distributions import Fixed, Poisson, Samples


def test_fit_duration_recovers_lognormal():
    rng = np.random.default_rng(0)
    x = rng.lognormal(np.log(90), 0.4, size=2000)
    fit = fit_duration(x)
    assert fit.name in {"lognormal", "gamma"}
    assert fit.distribution.mean_value() == pytest.approx(x.mean(), rel=0.05)


def test_fit_duration_small_samples():
    assert isinstance(fit_duration([5, 5]).distribution, Fixed)
    assert isinstance(fit_duration([3, 4, 8, 9, 12]).distribution, Samples)


def test_fit_count_poisson():
    rng = np.random.default_rng(1)
    assert isinstance(fit_count(rng.poisson(25, size=200)), Poisson)


def test_column_mapping():
    raw = pd.DataFrame(
        {"IEP": ["1", "1"], "Etape": ["a", "b"], "Horodatage": ["05/01/2026 08:00", "05/01/2026 08:30"]}
    )
    df = normalise(raw, ColumnMapping(case_id="IEP", activity="Etape", timestamp="Horodatage"))
    assert list(df.columns[:3]) == ["case_id", "activity", "timestamp"]
    assert df.timestamp.iloc[0].month == 1  # dayfirst


def test_missing_column_raises():
    with pytest.raises(ValueError, match="Colonnes obligatoires"):
        normalise(pd.DataFrame({"x": [1]}), ColumnMapping())


def test_build_pathway_from_synthetic_log():
    df = generate_bloc_log(days=40, cases_per_day=25, seed=3)
    assert variants(df)[0].share == 1.0
    pw, report = build_pathway(
        df, "chirurgie_programmee", "bloc", step_resources={"debut_intervention": {"salle_bloc": 1}}
    )
    assert len(pw.steps) == 8
    surgery = next(s for s in pw.steps if s.id == "debut_intervention")
    assert surgery.duration_min.mean_value() == pytest.approx(95, rel=0.15)
    assert surgery.resources == {"salle_bloc": 1}
    assert pw.arrivals.window.weekdays == [0, 1, 2, 3, 4]
    assert report.observed_mean_cases_per_day == pytest.approx(25, rel=0.15)
