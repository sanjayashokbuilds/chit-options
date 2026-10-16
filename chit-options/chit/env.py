"""The chit as ONE member sees it, when every other member bids myopically.

All amounts here are fractions of the pot (pot = 1). In a month with winning
discount d, every member pays (1 - d + c) / N. Check: N=10, d=0.30, c=0.05
gives 0.075, i.e. £75 of a £1,000 pot.

Why the state is small: rivals are identical and bid myopically, so a rival's
willingness depends only on (month, in need?). The rivals' whole situation is
then captured by
    n = how many rivals are still waiting for a pot (fixed by the month)
    k = how many of those are in need
and the member's own state is (month t, own need h, k).

Assumptions (flagged in the README):
- FULL information: the member knows k. Real members don't see each other's
  needs, so values computed with this are an upper bound.
- Two actions each month: "bid" (stay in the auction up to the cap) or "pass"
  (sit the auction out). A passing member never wins by lottery, and nobody
  bids just to push up the price others pay.
- Auction is English: a winner pays the highest rival willingness.
"""

from dataclasses import dataclass
from functools import lru_cache
from math import comb

from .mechanics import ChitParams
from .members import MemberParams, myopic_reservation


def payment(chit: ChitParams, discount: float) -> float:
    """What every member pays this month, as a fraction of the pot."""
    return (1 - discount + chit.commission) / chit.n_members


@dataclass(frozen=True)
class RivalBook:
    top: float           # highest rival willingness
    n_top: int           # how many rivals share it
    second: float        # the price if the member passes (2nd-highest rival, or c)
    p_needy_wins: float  # chance that a winning rival is one of those in need


def rival_book(chit: ChitParams, members: MemberParams, t: int, n: int, k: int) -> RivalBook:
    """What the n waiting rivals (k of them in need) are willing to pay in month t."""
    if not 0 <= k <= n or n < 1:
        raise ValueError(f"need 0 <= k <= n and n >= 1, got n={n}, k={k}")
    a = myopic_reservation(chit, members, t, True)    # each needy rival's limit
    b = myopic_reservation(chit, members, t, False)   # each other rival's limit
    if k > 0 and a > b:
        top, n_top, p_needy = a, k, 1.0
    elif k > 0:                     # a == b (both clipped): everyone ties
        top, n_top, p_needy = a, n, k / n
    else:
        top, n_top, p_needy = b, n, 0.0

    if n < 2:
        second = chit.commission    # a lone bidder pays the minimum
    elif n_top >= 2:
        second = top
    else:
        second = b                  # one needy rival on top, the rest below
    return RivalBook(top, n_top, second, p_needy)


def bid_outcome(chit: ChitParams, book: RivalBook) -> tuple[float, float]:
    """If the member stays in up to the cap: (chance of winning, price if they win)."""
    if book.top < chit.bid_cap:
        return 1.0, book.top                        # outbids every rival
    return 1.0 / (book.n_top + 1), chit.bid_cap     # lottery with the rivals at the cap


@lru_cache(maxsize=None)
def binomial_pmf(trials: int, p: float) -> tuple[float, ...]:
    """P(exactly j successes) for j = 0..trials. Cached: the solvers ask for
    the same few (trials, p) pairs millions of times."""
    return tuple(comb(trials, j) * p**j * (1 - p) ** (trials - j) for j in range(trials + 1))
