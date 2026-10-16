"""Results: the term structure of implied rates, sensitivities and the bid cap.

Exact, not simulated. When everyone follows the same table, the only thing
that matters each month is K = how many waiting members are in need. Given K,
the winning discount is fixed (ties only decide WHO wins, not the price), and
K next month depends only on K now. So K is a Markov chain: we push its
probability distribution forward month by month and read off exact averages.
The simulator is used in the tests to confirm these numbers.
"""

from dataclasses import dataclass, replace

import numpy as np

from . import equilibrium as eq
from .env import binomial_pmf
from .mechanics import ChitParams
from .members import MemberParams


@dataclass
class TermStructure:
    discount: np.ndarray    # E[winning discount] by month (month 0 = foreman, 0)
    forward: np.ndarray     # E[forward rate t -> t+1], monthly; NaN for month 0
    yield_end: np.ndarray   # E[yield from t to the end], monthly
    p_cap: np.ndarray       # chance the cap binds in month t
    needy_share: np.ndarray # E[share of waiting members in need] at month t's auction

    def peak_month(self, kind: str = "forward") -> int:
        """Month (from 1) where the average forward rate or yield to end is highest."""
        curve = self.forward[1:] if kind == "forward" else self.yield_end[1:-1]
        return int(np.nanargmax(curve) + 1)


def term_structure(chit: ChitParams, members: MemberParams, w) -> TermStructure:
    N, p, cap = chit.n_members, members.p_need, chit.bid_cap
    discount, p_cap, needy_share = np.zeros(N), np.zeros(N), np.zeros(N)
    yield_end = np.full(N, np.nan)
    forward = np.full(N - 1, np.nan)

    # Month 1: the N - 1 non-foreman members, each in need with prob 1-(1-p)^2.
    dist = np.array(binomial_pmf(N - 1, 1 - (1 - p) ** 2))
    prev_d = prev_dist = prev_T = None
    for t in range(1, N):
        nw = N - t
        d = np.zeros(nw + 1)
        T = np.zeros((nw + 1, nw))                     # next month: nw - 1 waiting
        for K in range(nw + 1):
            outcomes = eq.auction(chit, eq._groups(w, t, K, nw - K, K))
            d[K] = outcomes[0][2]                      # same price whoever wins
            for q, lab, _ in outcomes:
                k_after = K - (lab == "needy")
                if nw > 1:
                    for j, qj in enumerate(binomial_pmf(nw - 1 - k_after, p)):
                        T[K, k_after + j] += q * qj
        discount[t] = dist @ d
        p_cap[t] = dist @ (d >= cap - 1e-12)
        needy_share[t] = dist @ (np.arange(nw + 1) / nw)
        if t < N - 1:
            yield_end[t] = dist @ (((1 - chit.commission) / (1 - d)) ** (1 / (N - 1 - t)) - 1)
        if prev_d is not None:
            # E[(1 - d_{t}) / (1 - d_{t-1}) - 1], using the joint law of K_{t-1}, K_t
            ratio = (1 - d)[None, :] / (1 - prev_d)[:, None] - 1
            forward[t - 1] = np.sum(prev_dist[:, None] * prev_T * ratio)
        prev_d, prev_dist, prev_T = d, dist, T
        dist = dist @ T if nw > 1 else None
    return TermStructure(discount, forward, yield_end, p_cap, needy_share)


def annual(monthly):
    return (1 + np.asarray(monthly)) ** 12 - 1


@dataclass
class Scenario:
    label: str
    seat_value: float          # equilibrium seat value, fraction of the pot
    mean_forward: float        # average forward rate, months 1..N-2, annualised
    mean_yield: float          # average yield to end, months 1..N-2, annualised
    first_discount: float      # expected winning discount in month 1
    forward_peak: float        # peak month of the forward curve / N
    yield_peak: float          # peak month of the yield curve / N
    converged: bool
    deviation_gain: float


def run(chit: ChitParams, members: MemberParams, label="base"):
    e = eq.solve(chit, members)
    ts = term_structure(chit, members, e.w)
    N = chit.n_members
    sc = Scenario(label, e.value,
                  float(np.mean(annual(ts.forward[1:]))),
                  float(np.mean(annual(ts.yield_end[1:-1]))),
                  float(ts.discount[1]),
                  ts.peak_month("forward") / N, ts.peak_month("yield") / N,
                  e.converged, e.deviation_gain)
    return sc, ts, e


def sensitivity(chit, members, field_name: str, values):
    """Re-solve the equilibrium for each value of one setting (chit or member)."""
    out = []
    for v in values:
        if hasattr(chit, field_name):
            c, m = replace(chit, **{field_name: v}), members
        else:
            c, m = chit, replace(members, **{field_name: v})
        out.append(run(c, m, f"{field_name}={v}"))
    return out


def greek(chit, members, field_name: str, step: float) -> float:
    """Central finite difference of the equilibrium seat value wrt one setting."""
    base = getattr(chit, field_name, None)
    if base is None:
        base = getattr(members, field_name)
    up, down = sensitivity(chit, members, field_name, [base + step, base - step])
    return (up[0].seat_value - down[0].seat_value) / (2 * step)
