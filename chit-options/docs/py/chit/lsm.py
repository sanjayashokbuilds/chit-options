"""Longstaff-Schwartz least-squares Monte Carlo (LSM) for the same seat.

The DP computes "the value of waiting" exactly, by averaging over every
possible next state. That only works when the state is small. LSM instead
SIMULATES many futures and LEARNS the value of waiting by regression, so it
scales to richer states. Here we run it on the DP's own setting so the two
can be checked against each other.

1. Simulate n_paths futures in which the member keeps sitting out. Each path
   records, every month, the member's state (h, k) and what would happen if
   they bid that month instead: would they win, at what price, and what the
   payments still left after winning would be worth.
2. Go backwards from the last month. On each path we know the REALISED value
   of passing (this month's payment plus the path's value from next month) and
   of bidding. Regress (bid value - pass value) on basis functions of the
   state; bid wherever the fitted advantage is positive. Then set each path's
   value to the realised value of the action chosen. (Regression is used only
   to make decisions, never for the values themselves: that's the LSM trick.)
3. Value the learned rule on FRESH paths. Judging a rule on the paths that
   chose it flatters it, because it partly fits their noise.
"""

from dataclasses import dataclass

import numpy as np

from .env import bid_outcome, payment, rival_book
from .mechanics import ChitParams
from .members import MemberParams


@dataclass
class Paths:
    h0: np.ndarray          # own need in month 0, shape (paths,)
    h: np.ndarray           # own need in month t (if still waiting), (N, paths)
    k: np.ndarray           # needy rivals in month t, (N, paths)
    pass_price: np.ndarray  # discount if the member sits out month t
    wins: np.ndarray        # True if bidding in month t would win (lottery drawn)
    win_price: np.ndarray   # discount paid if bidding wins
    after_win: np.ndarray   # value at t+1 of the payments left after winning at t


def _rivals_month(rng, chit, members, t, n, k):
    """One month among n waiting rivals (k needy), vectorised over paths.
    Returns (price, needy_won) arrays."""
    books = [rival_book(chit, members, t, n, kk) for kk in range(n + 1)]
    price = np.array([b.second for b in books])[k]
    p_needy = np.array([b.p_needy_wins for b in books])[k]
    return price, rng.random(len(k)) < p_needy


def _add_needs(rng, k, n_waiting, p):
    """Rivals still waiting and not yet in need each get a need with prob p."""
    return k + rng.binomial(n_waiting - k, p)


def simulate_paths(rng, chit: ChitParams, members: MemberParams, n_paths: int) -> Paths:
    N, p = chit.n_members, members.p_need
    beta_save = 1 / (1 + members.r_save)
    h = np.zeros((N, n_paths), dtype=bool)
    k = np.zeros((N, n_paths), dtype=int)
    pass_price, win_price, after_win = (np.zeros((N, n_paths)) for _ in range(3))
    wins = np.zeros((N, n_paths), dtype=bool)

    # Months 0 and 1: two chances for each need to appear.
    h0 = rng.random(n_paths) < p
    h[1] = h0 | (rng.random(n_paths) < p)
    k[1] = rng.binomial(N - 2, 1 - (1 - p) ** 2, n_paths)

    for t in range(1, N - 1):
        n = N - t - 1                                   # other members waiting
        books = [rival_book(chit, members, t, n, kk) for kk in range(n + 1)]
        outcome = [bid_outcome(chit, b) for b in books]
        p_win = np.array([o[0] for o in outcome])[k[t]]
        win_price[t] = np.array([o[1] for o in outcome])[k[t]]
        wins[t] = rng.random(n_paths) < p_win

        # If the member won now: rivals-only months until the end.
        k_b, pv, disc = _add_needs(rng, k[t], n, p), 0.0, 1.0
        for s in range(t + 1, N):
            price, needy_won = _rivals_month(rng, chit, members, s, N - s, k_b)
            pv = pv - disc * payment(chit, price)
            disc *= beta_save
            k_b = _add_needs(rng, k_b - needy_won, N - s - 1, p)
        after_win[t] = pv

        # The path itself: the member sits out and a rival wins.
        pass_price[t], needy_won = _rivals_month(rng, chit, members, t, n, k[t])
        k[t + 1] = _add_needs(rng, k[t] - needy_won, n - 1, p)
        h[t + 1] = h[t] | (rng.random(n_paths) < p)
    return Paths(h0, h, k, pass_price, wins, win_price, after_win)


def basis(kind: str, h, k, n: int) -> np.ndarray:
    """Regression features of the state. 'indicator': one column per (h, k), so
    the fit is the exact average in each state. 'poly': a few smooth terms."""
    if kind == "indicator":
        cols = [(h == hh) & (k == kk) for hh in (0, 1) for kk in range(n + 1)]
        return np.column_stack(cols).astype(float)
    if kind == "poly":                 # a cubic in k, separately for h = 0 and h = 1
        x = k / max(n, 1)
        cols = [(h == hh) * x**j for hh in (0, 1) for j in range(4)]
        return np.column_stack(cols).astype(float)
    raise ValueError(f"unknown basis {kind!r}")


def _backward(chit, members, paths: Paths, kind: str, coefs=None):
    """Realised path values under the learned (coefs=None) or a given rule."""
    N, cap = chit.n_members, chit.bid_cap
    beta_save = 1 / (1 + members.r_save)
    beta = lambda h: np.where(h, 1 / (1 + members.r_borrow), beta_save)
    learned = {}
    value = np.full(paths.h0.shape, (1 - chit.commission) - payment(chit, chit.commission))
    for t in range(N - 2, 0, -1):
        h, k, n = paths.h[t], paths.k[t], N - t - 1
        pass_v = -payment(chit, paths.pass_price[t]) + beta(h) * value
        won_v = (1 - paths.win_price[t]) - payment(chit, paths.win_price[t]) \
            + beta_save * paths.after_win[t]
        lost_v = -payment(chit, cap) + beta(h) * value     # lost the lottery at the cap
        bid_v = np.where(paths.wins[t], won_v, lost_v)

        X = basis(kind, h, k, n)
        if coefs is None:
            learned[t] = np.linalg.lstsq(X, bid_v - pass_v, rcond=None)[0]
        do_bid = X @ (learned[t] if coefs is None else coefs[t]) > 0
        value = np.where(do_bid, bid_v, pass_v)
    seat = -1 / N + beta(paths.h0) * value
    return seat, learned


@dataclass
class LSMResult:
    value: float     # out-of-sample seat value, fraction of the pot
    se: float        # its Monte Carlo standard error
    in_sample: float # value on the training paths (biased upwards)
    coefs: dict      # learned regression coefficients per month


def solve(chit: ChitParams, members: MemberParams, n_paths=50_000, kind="indicator", seed=0):
    if not chit.foreman_first:
        raise ValueError("LSM assumes the foreman takes month 0")
    rng = np.random.default_rng(seed)
    train = simulate_paths(rng, chit, members, n_paths)
    seat_in, coefs = _backward(chit, members, train, kind)
    test = simulate_paths(rng, chit, members, n_paths)
    seat_out, _ = _backward(chit, members, test, kind, coefs)
    return LSMResult(float(seat_out.mean()), float(seat_out.std() / np.sqrt(n_paths)),
                     float(seat_in.mean()), coefs)


def evaluate_table(chit: ChitParams, members: MemberParams, bid, n_paths=50_000, seed=0):
    """Simulated value of a given policy table bid[t, h, k] (e.g. the DP's).
    Returns (mean, standard error)."""
    N = chit.n_members
    coefs = {t: np.array([1.0 if bid[t, hh, kk] else -1.0
                          for hh in (0, 1) for kk in range(N - t)])
             for t in range(1, N - 1)}
    paths = simulate_paths(np.random.default_rng(seed), chit, members, n_paths)
    seat, _ = _backward(chit, members, paths, "indicator", coefs)
    return float(seat.mean()), float(seat.std() / np.sqrt(n_paths))


def policy_table(chit: ChitParams, result: LSMResult, kind="indicator") -> np.ndarray:
    """The learned rule as bid[t, h, k], comparable with the DP's table."""
    N = chit.n_members
    bid = np.zeros((N, 2, N), dtype=bool)
    bid[N - 1, :, 0] = True
    for t, c in result.coefs.items():
        n = N - t - 1
        for h in (0, 1):
            ks = np.arange(n + 1)
            bid[t, h, : n + 1] = basis(kind, np.full(n + 1, h), ks, n) @ c > 0
    return bid
