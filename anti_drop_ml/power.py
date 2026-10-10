"""Approximate per-arm sample size: independent individuals, equal allocation.

Not a full analysis plan: account for clustering, event rate, ITT and guardrails.
"""
from math import ceil, isfinite, sqrt
from statistics import NormalDist


def required_n_two_proportions(baseline_rate: float, expected_uplift_pp: float, alpha: float = .05, power: float = .80, dropout_rate: float = .0) -> int:
    values = (baseline_rate, expected_uplift_pp, alpha, power, dropout_rate)
    if not all(isinstance(v, (float, int)) and not isinstance(v, bool) and isfinite(v) for v in values):
        raise ValueError('finite numeric parameters required')
    target = baseline_rate + expected_uplift_pp / 100
    if not (0 < baseline_rate < 1 and 0 < target < 1 and expected_uplift_pp != 0 and 0 < alpha < 1 and .5 < power < 1 and 0 <= dropout_rate < 1):
        raise ValueError('invalid rates, uplift, alpha, power or dropout')
    pooled = (baseline_rate + target) / 2
    z_alpha = NormalDist().inv_cdf(1-alpha/2)
    z_power = NormalDist().inv_cdf(power)
    n = (z_alpha*sqrt(2*pooled*(1-pooled)) + z_power*sqrt(baseline_rate*(1-baseline_rate)+target*(1-target)))**2 / (target-baseline_rate)**2
    return ceil(n / (1-dropout_rate))
