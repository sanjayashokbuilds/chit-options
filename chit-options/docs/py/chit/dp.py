"""Dynamic programming: value one seat and find when bidding is optimal.

Start in the last month, where there is no choice, and step back one month at
a time. In every state the member compares bidding with passing; the value of
passing uses next month's values, which are already known. This is the same
backward induction used to price American options on a tree.

Two value tables (fractions of the pot):
    U[t, k]    : member has ALREADY won. Only payments are left, no decisions.
                 k = needy rivals among the N - t still waiting in month t.
    V[t, h, k] : member is still waiting, own need h (0/1), k needy among the
                 N - t - 1 other waiting members.
Discounting: next month's money is worth 1/(1 + r) now, with r = r_borrow
while the member is in need and r_save otherwise (including after winning).

Requires foreman_first: member 0 is the foreman, the valued seat is any other.
"""

from dataclasses import dataclass

import numpy as np

from .env import bid_outcome, binomial_pmf, payment, rival_book
from .mechanics import ChitParams
from .members import MemberParams


@dataclass
class DPResult:
    value: float        # seat value at month 0, fraction of the pot
    V: np.ndarray       # V[t, h, k], NaN where the state can't exist
    U: np.ndarray       # U[t, k]
    bid: np.ndarray     # bid[t, h, k] = True where the policy bids


def _expected_next(table_next, k_after: int, n_next: int, p: float) -> float:
    """Average of table_next[k] once each of the n_next - k_after rivals not
    yet in need gets a need with probability p."""
    probs = binomial_pmf(n_next - k_after, p)
    return sum(q * table_next[k_after + j] for j, q in enumerate(probs))


def _own_need_next(h: int, p: float):
    """(next month's own need, probability): a need stays; otherwise appears with prob p."""
    return [(1, 1.0)] if h else [(1, p), (0, 1 - p)]


def _solve(chit: ChitParams, members: MemberParams, policy=None) -> DPResult:
    if not chit.foreman_first:
        raise ValueError("the DP assumes the foreman takes month 0")
    N, c, p = chit.n_members, chit.commission, members.p_need
    beta_save = 1 / (1 + members.r_save)
    beta = [beta_save, 1 / (1 + members.r_borrow)]   # beta[h]

    # --- After winning: payments only. U[N, :] = 0 (the chit is over). ---
    U = np.full((N + 1, N + 1), np.nan)
    U[N, :] = 0.0
    for t in range(N - 1, 0, -1):
        n = N - t                                    # rivals waiting this month
        for k in range(n + 1):
            book = rival_book(chit, members, t, n, k)
            cont = 0.0
            for needy_won, q in ((1, book.p_needy_wins), (0, 1 - book.p_needy_wins)):
                if q > 0:
                    cont += q * _expected_next(U[t + 1], k - needy_won, n - 1, p)
            U[t, k] = -payment(chit, book.second) + beta_save * cont

    # --- Still waiting. Last month: alone, wins at the minimum discount. ---
    V = np.full((N, 2, N), np.nan)
    bid = np.zeros((N, 2, N), dtype=bool)
    V[N - 1, :, 0] = (1 - c) - payment(chit, c)
    bid[N - 1, :, 0] = True

    for t in range(N - 2, 0, -1):
        n = N - t - 1                                # other members still waiting
        for h in (0, 1):
            for k in range(n + 1):
                book = rival_book(chit, members, t, n, k)

                def rival_wins_at(price):
                    """A rival takes this month's pot; the member keeps waiting."""
                    cont = 0.0
                    for needy_won, q in ((1, book.p_needy_wins), (0, 1 - book.p_needy_wins)):
                        if q == 0:
                            continue
                        k_after = k - needy_won
                        for h_next, qh in _own_need_next(h, p):
                            cont += q * qh * _expected_next(V[t + 1, h_next], k_after, n - 1, p)
                    return -payment(chit, price) + beta[h] * cont

                pass_value = rival_wins_at(book.second)

                p_win, price = bid_outcome(chit, book)
                win_value = (1 - price) - payment(chit, price) \
                    + beta_save * _expected_next(U[t + 1], k, n, p)
                bid_value = p_win * win_value
                if p_win < 1:                        # lost the lottery at the cap
                    bid_value += (1 - p_win) * rival_wins_at(chit.bid_cap)

                choose_bid = bid_value > pass_value if policy is None else bool(policy[t, h, k])
                bid[t, h, k] = choose_bid
                V[t, h, k] = bid_value if choose_bid else pass_value

    # --- Month 0: the foreman's month. Everyone pays 1/N. ---
    q_rival = 1 - (1 - p) ** 2       # a rival has a need by month 1 (two chances)
    rivals_at_1 = N - 2
    value = 0.0
    for h0, q0 in ((1, p), (0, 1 - p)):
        at_1 = 0.0
        for h1, q1 in _own_need_next(h0, p):
            at_1 += q1 * _expected_next(V[1, h1], 0, rivals_at_1, q_rival)
        value += q0 * (-1 / N + beta[h0] * at_1)
    return DPResult(value, V, U, bid)


def solve(chit: ChitParams, members: MemberParams) -> DPResult:
    """Optimal policy and the seat's value."""
    return _solve(chit, members)


def evaluate_policy(chit: ChitParams, members: MemberParams, policy) -> float:
    """Value of following a GIVEN policy (policy[t, h, k] = True means bid)."""
    return _solve(chit, members, np.asarray(policy, dtype=bool)).value
