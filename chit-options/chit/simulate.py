"""Play out whole chit groups month by month.

Each month: members still waiting may develop a need, each one states how much
of the pot they'd give up (their strategy), and an auction picks the winner
and the discount.

Auction formats (which one real chits use is still to verify):
- "english": open ascending bidding. Bidding stops when the second-keenest
  member drops out, so the winner pays the SECOND-highest willingness.
- "sealed": sealed bids, highest bid wins and pays its own bid.
In both, the discount is kept within [commission, bid_cap], and ties
(e.g. several members at the cap) are broken by lottery.
"""

from dataclasses import dataclass

import numpy as np

from .mechanics import ChitParams
from .members import MemberParams, update_needs


def run_auction(rng, bidders, willing, chit: ChitParams, fmt: str = "english"):
    """bidders: member indices still eligible; willing: their max discounts.
    Returns (winner, discount)."""
    bidders, willing = np.asarray(bidders), np.asarray(willing, dtype=float)
    willing = np.clip(willing, chit.commission, chit.bid_cap)
    top = willing.max()
    winner = int(rng.choice(bidders[willing == top]))   # lottery among the keenest

    if len(bidders) == 1:
        discount = chit.commission                      # nobody to compete with
    elif fmt == "english":
        discount = np.sort(willing)[-2]                 # second-highest willingness
    elif fmt == "sealed":
        discount = top
    else:
        raise ValueError(f"unknown auction format {fmt!r}")
    return winner, float(discount)


@dataclass
class ChitPath:
    winners: np.ndarray     # winners[t] = member who took month t's pot
    discounts: np.ndarray   # discounts[t] = winning discount in month t
    needs: np.ndarray       # needs[i, t] = member i was in need at month t's auction


def simulate_chit(rng, chit: ChitParams, members: MemberParams, strategy, fmt="english"):
    n = chit.n_members
    won = np.zeros(n, dtype=bool)
    in_need = np.zeros(n, dtype=bool)
    winners, discounts = np.zeros(n, dtype=int), np.zeros(n)
    needs = np.zeros((n, n), dtype=bool)

    for t in range(n):
        in_need = update_needs(rng, in_need, ~won, members.p_need)
        needs[:, t] = in_need
        if t == 0 and chit.foreman_first:
            winner, discount = 0, 0.0                   # foreman's month, no auction
        else:
            bidders = np.flatnonzero(~won)
            willing = [strategy(t, in_need[i]) for i in bidders]
            winner, discount = run_auction(rng, bidders, willing, chit, fmt)
        winners[t], discounts[t] = winner, discount
        won[winner] = True
        in_need[winner] = False                         # the pot meets the need
    return ChitPath(winners, discounts, needs)


def simulate_many(chit, members, strategy, n_sims: int, seed: int = 0, fmt="english"):
    """Run n_sims independent groups. Returns a list of ChitPath."""
    rng = np.random.default_rng(seed)
    return [simulate_chit(rng, chit, members, strategy, fmt) for _ in range(n_sims)]
