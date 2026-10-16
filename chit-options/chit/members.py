"""Why members bid: outside interest rates and random cash needs.

The member model (a modelling choice, flagged in the README):
- Outside the chit, a member can borrow at r_borrow or save at r_save per month,
  with r_borrow > r_save. That gap is why chits exist at all.
- Each month, a member who hasn't won yet and isn't already in need becomes
  "in need" with probability p_need (an emergency, a wedding, a field to buy).
  A need lasts until the member wins a pot.
- A member in need values cash now at r_borrow (the pot replaces an outside
  loan). A member not in need values it at r_save (the pot replaces savings).

A strategy is any function (month t, in_need) -> the most of the pot (as a
fraction) the member is willing to give up this month.
"""

from dataclasses import dataclass

import numpy as np

from .mechanics import ChitParams


@dataclass(frozen=True)
class MemberParams:
    r_borrow: float = 0.02  # monthly outside borrowing rate (about 27% a year)
    r_save: float = 0.005   # monthly outside saving rate (about 6% a year)
    p_need: float = 0.10    # monthly chance a member without a need gets one

    def __post_init__(self):
        if not 0 <= self.r_save <= self.r_borrow:
            raise ValueError("need 0 <= r_save <= r_borrow")
        if not 0 <= self.p_need <= 1:
            raise ValueError("p_need must be a probability")

    def rate(self, in_need: bool) -> float:
        return self.r_borrow if in_need else self.r_save


def update_needs(rng, in_need, eligible, p_need: float):
    """Start of a month: members still waiting for a pot may develop a need."""
    new_need = eligible & ~in_need & (rng.random(len(in_need)) < p_need)
    return in_need | new_need


def myopic_reservation(chit: ChitParams, members: MemberParams, t: int, in_need: bool) -> float:
    """Largest discount worth paying to win in month t instead of in the last month.

    Winning at t pays pot*(1-d) now; the fallback of winning last pays
    pot*(1-commission) after k more months (payments are identical either way).
    Indifference: (1-d) * (1+r)^k = 1 - commission.

    "Myopic" because it ignores the chance of winning in between at a lower
    price. That chance is the option's time value; the DP adds it back later.
    """
    k = chit.n_members - 1 - t
    r = members.rate(in_need)
    d = 1 - (1 - chit.commission) / (1 + r) ** k
    return min(max(d, chit.commission), chit.bid_cap)


def myopic_strategy(chit: ChitParams, members: MemberParams):
    return lambda t, in_need: myopic_reservation(chit, members, t, in_need)


def lottery_strategy(chit: ChitParams):
    """Everyone offers the minimum, so the winner is drawn by lot."""
    return lambda t, in_need: chit.commission
