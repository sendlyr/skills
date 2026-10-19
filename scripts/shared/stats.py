"""Canonical shared block: the statistics used across scripts.

See ``docs/data-contracts.md`` ("Statistics used"). Embedded verbatim in the scripts
that need it; sync with ``python3 scripts/sync_shared_blocks.py``.
"""

# --- BEGIN shared:stats (generated from scripts/shared/stats.py; do not edit here) ---
import math as _smath
from statistics import NormalDist as _NormalDist

Z95 = 1.959963984540054


def z_for(confidence=0.95):
    """Two-sided critical value, e.g. 1.96 for 0.95."""
    return _NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def wilson(k, n, z=Z95):
    """Wilson score interval for k successes out of n. (nan, nan) when n == 0."""
    if n <= 0:
        return (_smath.nan, _smath.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * _smath.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((centre - half) / denom, (centre + half) / denom)


def newcombe_diff(k1, n1, k2, n2, z=Z95):
    """Difference p1 - p2 with Newcombe's hybrid score interval (method 10).
    Returns (diff, lo, hi); all nan if either group is empty."""
    if n1 <= 0 or n2 <= 0:
        return (_smath.nan, _smath.nan, _smath.nan)
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    d = p1 - p2
    lo = d - _smath.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = d + _smath.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return (d, lo, hi)


def two_prop_p(k1, n1, k2, n2):
    """Two-sided pooled z-test p-value for p1 == p2. 1.0 when undefined."""
    if n1 <= 0 or n2 <= 0:
        return 1.0
    pool = (k1 + k2) / (n1 + n2)
    se = _smath.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return 1.0
    z = (k1 / n1 - k2 / n2) / se
    return _smath.erfc(abs(z) / _smath.sqrt(2))


def _log_hypergeom(a, row1, col1, n):
    lg = _smath.lgamma
    return (lg(row1 + 1) + lg(n - row1 + 1) + lg(col1 + 1) + lg(n - col1 + 1)
            - lg(n + 1) - lg(a + 1) - lg(row1 - a + 1) - lg(col1 - a + 1) - lg(n - row1 - col1 + a + 1))


def fisher_exact(a, b, c, d):
    """Two-sided Fisher exact p-value for the 2x2 table [[a, b], [c, d]]."""
    row1, col1, n = a + b, a + c, a + b + c + d
    if n == 0:
        return 1.0
    lo, hi = max(0, row1 + col1 - n), min(row1, col1)
    log_obs = _log_hypergeom(a, row1, col1, n)
    total = 0.0
    for x in range(lo, hi + 1):
        lp = _log_hypergeom(x, row1, col1, n)
        if lp <= log_obs + 1e-7:
            total += _smath.exp(lp)
    return min(1.0, total)


def holm(pvalues):
    """Holm step-down adjusted p-values, in the original order."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def chi2_1df_p(x):
    """Upper-tail p-value of a chi-square statistic with 1 degree of freedom."""
    if x <= 0:
        return 1.0
    return _smath.erfc(_smath.sqrt(x / 2))


def srm_p(n_treatment, n_control, allocation_treatment):
    """Sample-ratio-mismatch p-value (chi-square goodness of fit, 1 df)."""
    n = n_treatment + n_control
    if n == 0:
        return 1.0
    e_t, e_c = n * allocation_treatment, n * (1 - allocation_treatment)
    x = (n_treatment - e_t) ** 2 / e_t + (n_control - e_c) ** 2 / e_c
    return chi2_1df_p(x)


def sample_size_per_arm(p1, p2, alpha=0.05, power=0.8, allocation_treatment=0.5):
    """Users needed in the control arm (p1) and treatment arm (p2) to detect p2 - p1,
    two-sided, normal approximation. Returns (n_control, n_treatment)."""
    if p1 == p2:
        return (_smath.inf, _smath.inf)
    k = allocation_treatment / (1 - allocation_treatment)      # n_t = k * n_c
    za = _NormalDist().inv_cdf(1 - alpha / 2)
    zb = _NormalDist().inv_cdf(power)
    pbar = (p1 + k * p2) / (1 + k)
    num = (za * _smath.sqrt(pbar * (1 - pbar) * (1 + 1 / k))
           + zb * _smath.sqrt(p1 * (1 - p1) + p2 * (1 - p2) / k)) ** 2
    n_c = _smath.ceil(num / (p2 - p1) ** 2)
    return (n_c, _smath.ceil(k * n_c))
# --- END shared:stats ---
