"""Core mechanics of one chit group: who pays what, and who receives what, each month.

Conventions (each one is a modelling choice, flagged in the README):
- Bids are discounts expressed as a FRACTION of the pot, e.g. 0.30 = give up 30%.
- In every auction month the foreman's commission (c * pot) comes out of the
  winning discount, so the smallest legal bid is c. The rest of the discount is
  split equally among ALL N members (winner included) as a dividend.
- If foreman_first, member 0 is the foreman's seat and takes month 0's pot in
  full: no auction, no discount, no commission.
- Month t's payments and payout happen at the same moment (end of month t).
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ChitParams:
    n_members: int              # N: number of members = number of months
    instalment: float           # m: what each member owes per month before dividend
    commission: float = 0.05    # c: foreman's cut, fraction of pot (legal cap: to verify)
    bid_cap: float = 0.40       # kappa: max discount, fraction of pot (to verify)
    foreman_first: bool = True  # foreman takes month 0's pot

    def __post_init__(self):
        if self.n_members < 2:
            raise ValueError("need at least 2 members")
        if not 0 <= self.commission <= self.bid_cap < 1:
            raise ValueError("need 0 <= commission <= bid_cap < 1")

    @property
    def pot(self) -> float:
        return self.n_members * self.instalment


def settle_month(params: ChitParams, discount: float) -> tuple[float, float, float]:
    """One auction month. Returns (payout to winner, payment per member, commission)."""
    if not params.commission <= discount <= params.bid_cap:
        raise ValueError(f"discount {discount} outside [commission, bid_cap]")
    pot = params.pot
    commission = params.commission * pot
    dividend_each = (discount * pot - commission) / params.n_members
    return pot * (1 - discount), params.instalment - dividend_each, commission


def monthly_settlements(params: ChitParams, discounts):
    """settle_month for every month of the chit.

    discounts[t] = winning discount in month t (ignored in the foreman's month).
    Returns three arrays of length N: payouts, payments (per member), commissions.
    """
    n = params.n_members
    if len(discounts) != n:
        raise ValueError(f"need {n} discounts, got {len(discounts)}")
    payouts, payments, commissions = np.zeros(n), np.zeros(n), np.zeros(n)
    for t in range(n):
        if t == 0 and params.foreman_first:
            payouts[t], payments[t], commissions[t] = params.pot, params.instalment, 0.0
        else:
            payouts[t], payments[t], commissions[t] = settle_month(params, discounts[t])
    return payouts, payments, commissions


def cash_flow_matrix(params: ChitParams, winners, discounts):
    """Every member's cash flow in every month, for one complete auction path.

    winners[t] = index of the member who takes the pot in month t.

    Returns (flows, commissions):
      flows[i, t]    = member i's net cash in month t (+ received, - paid)
      commissions[t] = what the foreman earned in month t
    """
    n = params.n_members
    winners = list(winners)
    if sorted(winners) != list(range(n)):
        raise ValueError("each member must win exactly once")
    if params.foreman_first and winners[0] != 0:
        raise ValueError("foreman (member 0) must win month 0")

    payouts, payments, commissions = monthly_settlements(params, discounts)
    flows = np.tile(-payments, (n, 1))      # every member pays the same each month...
    for t in range(n):
        flows[winners[t], t] += payouts[t]  # ...and the month's winner also gets the pot
    return flows, commissions
