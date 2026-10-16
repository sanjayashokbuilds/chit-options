"""Effective interest rate (IRR) of a member's monthly cash flows.

The IRR is the monthly rate r that makes the present value of the flows zero:
    NPV(r) = sum_t flows[t] / (1 + r)^t = 0

Warning: a chit member typically pays, then receives, then pays again
(signs - - + - -). Two sign changes means there can be TWO rates that solve
NPV = 0. So we scan a grid for every root instead of assuming there is one.
"""

import numpy as np


def npv(rate: float, flows) -> float:
    t = np.arange(len(flows))
    return float(np.sum(np.asarray(flows) / (1 + rate) ** t))


def _bisect(f, lo: float, hi: float, tol: float = 1e-12) -> float:
    """Find a root of f between lo and hi, given f(lo) and f(hi) differ in sign."""
    f_lo = f(lo)
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if (f(mid) > 0) == (f_lo > 0):
            lo, f_lo = mid, f(mid)
        else:
            hi = mid
    return (lo + hi) / 2


def irr_roots(flows, lo: float = -0.5, hi: float = 0.5, grid: int = 2001) -> list[float]:
    """All monthly IRRs in [lo, hi]."""
    f = lambda r: npv(r, flows)
    rates = np.linspace(lo, hi, grid)
    values = [f(r) for r in rates]
    roots = []
    for i in range(grid - 1):
        if values[i] == 0:
            roots.append(float(rates[i]))
        elif values[i] * values[i + 1] < 0:
            roots.append(_bisect(f, rates[i], rates[i + 1]))
    return roots


def monthly_irr(flows) -> float:
    """The unique monthly IRR in a plausible range; raises if not unique."""
    roots = irr_roots(flows)
    if len(roots) != 1:
        raise ValueError(f"expected one IRR, found {len(roots)}: {roots}")
    return roots[0]


def annualise(monthly_rate: float) -> float:
    return (1 + monthly_rate) ** 12 - 1
