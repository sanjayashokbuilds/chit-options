"""Symmetric equilibrium: every member bids optimally, knowing everyone else does too.

A strategy is a WILLINGNESS table w[t, h, k]: the largest discount a member
accepts in month t, given their own need h (0/1) and k = how many of the OTHER
waiting members are in need. Everyone uses the same table (members are identical).

Best response. In an English auction you stay in while winning at the current
price beats dropping out. At price d:
    win  : (1 - d) - payment(d) + beta_save * E[value after winning]
    lose :         - payment(d) + beta_h    * E[value of still waiting]
payment(d) is in both, so the price at which you're indifferent is
    d* = 1 - (beta_h * E[waiting] - beta_save * E[won])
i.e. one minus how much more it's worth to still hold the seat than to have
used it. (With "won" = "win last month", this is exactly the myopic rule.)

Fixed point. Start from the myopic table; compute the best response to the
current table; move part of the way towards it (damping, so it doesn't
oscillate); repeat until the table stops changing. Then check that no member
can gain by deviating, and that different starting tables end in the same place.

Same assumptions as the DP (full information about needs, no bidding just to
raise others' price), plus: a member drops out at their indifference price.
"""

from dataclasses import dataclass, field

import numpy as np

from .env import binomial_pmf, payment
from .mechanics import ChitParams
from .members import MemberParams, myopic_reservation


def auction(chit: ChitParams, groups):
    """groups: [(label, willingness, how many bidders)]. Highest willingness wins
    (lottery among ties); price = second-highest willingness among all bidders,
    or the commission if there's only one bidder.
    Returns [(probability, winner's label, price)]."""
    live = [(lab, w, n) for lab, w, n in groups if n > 0]
    total = sum(n for _, _, n in live)
    top = max(w for _, w, _ in live)
    at_top = [(lab, n) for lab, w, n in live if w == top]
    m = sum(n for _, n in at_top)
    if total == 1:
        price = chit.commission
    elif m >= 2:
        price = top
    else:
        price = max(w for _, w, _ in live if w < top)
    return [(n / m, lab, price) for lab, n in at_top]


def _groups(w, t: int, needy: int, fine: int, K: int):
    """Bidding groups for the waiting members other than the valued one.
    K = needy among ALL waiting members, so a needy member sees K - 1 other
    needy members and a fine member sees K."""
    groups = []
    if needy:
        groups.append(("needy", w[t, 1, K - 1], needy))
    if fine:
        groups.append(("fine", w[t, 0, K], fine))
    return groups


def _next(table_next, k_after: int, n_next: int, p: float) -> float:
    """Average of table_next[k] after each of the n_next - k_after waiting
    members not yet in need gets a need with probability p."""
    return sum(q * table_next[k_after + j]
               for j, q in enumerate(binomial_pmf(n_next - k_after, p)))


def _own_need_next(h: int, p: float):
    return [(1, 1.0)] if h else [(1, p), (0, 1 - p)]


@dataclass
class Pass:
    value: float        # seat value at month 0, fraction of the pot
    V: np.ndarray       # V[t, h, k] while waiting
    U: np.ndarray       # U[t, K] after winning (K = needy among the N - t waiting)
    x: np.ndarray       # the valued member's willingness table


def backward(chit: ChitParams, members: MemberParams, w, respond: bool) -> Pass:
    """Values for ONE member when all others follow table w.
    respond=True: that member best-responds. False: they also follow w."""
    if not chit.foreman_first:
        raise ValueError("assumes the foreman takes month 0")
    N, c, cap, p = chit.n_members, chit.commission, chit.bid_cap, members.p_need
    beta_save = 1 / (1 + members.r_save)
    beta = (beta_save, 1 / (1 + members.r_borrow))

    # After winning: only payments. Rivals play among themselves.
    U = np.full((N + 1, N + 1), np.nan)
    U[N, :] = 0.0
    for t in range(N - 1, 0, -1):
        nw = N - t                                        # rivals waiting
        for K in range(nw + 1):
            groups = _groups(w, t, K, nw - K, K)
            U[t, K] = sum(q * (-payment(chit, d)
                               + beta_save * _next(U[t + 1], K - (lab == "needy"), nw - 1, p))
                          for q, lab, d in auction(chit, groups))

    V = np.full((N, 2, N), np.nan)
    x = np.full((N, 2, N), np.nan)
    V[N - 1, :, 0] = (1 - c) - payment(chit, c)           # alone: wins at the minimum
    x[N - 1, :, 0] = c
    for t in range(N - 2, 0, -1):
        n = N - t - 1                                     # other members waiting
        for h in (0, 1):
            for k in range(n + 1):
                K = k + h                                 # needy among ALL waiting
                rivals = _groups(w, t, k, n - k, K)
                after_win = beta_save * _next(U[t + 1], k, n, p)
                after_loss = {}
                for lab, needy_won in (("needy", 1), ("fine", 0)):
                    if (k if needy_won else n - k) > 0:
                        after_loss[lab] = beta[h] * sum(
                            qh * _next(V[t + 1, h2], k - needy_won, n - 1, p)
                            for h2, qh in _own_need_next(h, p))

                if respond:   # indifference price against whichever rival would win
                    top_rival = sum(q * after_loss[lab] for q, lab, _ in auction(chit, rivals))
                    mine = float(np.clip(1 - (top_rival - after_win), c, cap))
                else:
                    mine = float(w[t, h, k])
                x[t, h, k] = mine

                total = 0.0
                for q, lab, d in auction(chit, [("me", mine, 1)] + rivals):
                    if lab == "me":
                        total += q * ((1 - d) - payment(chit, d) + after_win)
                    else:
                        total += q * (-payment(chit, d) + after_loss[lab])
                V[t, h, k] = total

    # Month 0: the foreman's month; then two chances for each need to appear.
    q_rival = 1 - (1 - p) ** 2
    value = sum(q0 * (-1 / N + beta[h0] * sum(
                    q1 * _next(V[1, h1], 0, N - 2, q_rival) for h1, q1 in _own_need_next(h0, p)))
                for h0, q0 in ((1, p), (0, 1 - p)))
    return Pass(value, V, U, x)


def valid_mask(N: int) -> np.ndarray:
    """True where w[t, h, k] is a real decision: months 1..N-2, k <= N-t-1."""
    mask = np.zeros((N, 2, N), dtype=bool)
    for t in range(1, N - 1):
        mask[t, :, : N - t] = True
    return mask


def myopic_table(chit: ChitParams, members: MemberParams) -> np.ndarray:
    N = chit.n_members
    w = np.full((N, 2, N), np.nan)
    for t in range(1, N - 1):
        for h in (0, 1):
            w[t, h, : N - t] = myopic_reservation(chit, members, t, bool(h))
    w[N - 1, :, 0] = chit.commission
    return w


@dataclass
class Equilibrium:
    w: np.ndarray                 # equilibrium willingness table
    value: float                  # seat value when everyone follows w
    converged: bool
    iterations: int
    changes: list = field(default_factory=list)  # largest table change per iteration
    deviation_gain: float = 0.0   # best-response value minus equilibrium value (>= 0)


def solve(chit: ChitParams, members: MemberParams, start=None, damping=0.5,
          tol=1e-10, max_iter=2000) -> Equilibrium:
    mask = valid_mask(chit.n_members)
    w = myopic_table(chit, members) if start is None else np.array(start, dtype=float)
    changes, converged = [], False
    for it in range(1, max_iter + 1):
        br = backward(chit, members, w, respond=True).x
        change = float(np.max(np.abs(br[mask] - w[mask])))
        changes.append(change)
        w[mask] = w[mask] + damping * (br[mask] - w[mask])
        if change < tol:
            converged = True
            break
    follow = backward(chit, members, w, respond=False).value
    gain = backward(chit, members, w, respond=True).value - follow
    return Equilibrium(w, follow, converged, it, changes, gain)


class TableStrategy:
    """Lets the month-by-month simulator play a willingness table."""
    uses_k = True

    def __init__(self, w):
        self.w = w

    def __call__(self, t, in_need, k):
        return float(self.w[t, int(in_need), k])
