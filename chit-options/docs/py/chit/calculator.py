"""Bidding calculator: should I bid this month, and up to how much?

1. Belief about the room. From the winning discounts so far, infer how many
   waiting members are probably in need. The number in need follows a Markov
   chain (see analysis.py) and each month's winning discount depends on it, so
   each past discount is evidence. Bayes' rule month by month:
       belief before month s  x  P(observed discount | K needy)  ->  update,
   then push the belief through the chain to the next month. (This is a
   hidden Markov model forward filter.)
2. Your limit. Your best-response willingness from the equilibrium, averaged
   over that belief. You can enter your own outside rates.
3. What to expect. Your chance of winning at that limit, the expected price,
   and what your position is worth now.

Approximations (flagged in the README):
- The equilibrium assumes members know how many others are in need; here that
  knowledge is replaced by a belief, and the limit is the belief-weighted
  average of the full-information limits.
- Real bids won't match model prices exactly, so an observed discount is
  compared with the model's price with a tolerance obs_sd (default 2% of pot).
"""

from dataclasses import dataclass, replace

import numpy as np

from . import analysis as an
from . import equilibrium as eq
from .mechanics import ChitParams
from .members import MemberParams


def needy_belief(chit: ChitParams, market: MemberParams, w, history, obs_sd=0.02):
    """P(K of the waiting members are in need) at the month after `history`.
    history = winning discounts of months 1, 2, ... (month 0 is the foreman's)."""
    dist = an.month1_prior(chit, market)
    for s, d_obs in enumerate(history, start=1):
        d, T = an.month_law(chit, market, w, s)
        log_like = -0.5 * ((d_obs - d) / obs_sd) ** 2
        post = dist * np.exp(log_like - log_like.max())   # rescaled: never all zero
        dist = (post / post.sum()) @ T
    return dist


@dataclass
class Advice:
    month: int
    limit: float            # most of the pot worth giving up this month (fraction)
    limit_amount: float     # the same, in currency
    p_win: float            # chance of winning this month if you bid up to the limit
    expected_price: float   # expected discount if you win (NaN if you can't win)
    position_value: float   # present value of your remaining cash flows, currency
    belief: np.ndarray      # P(K in need among the waiting members)
    message: str


def advise(chit: ChitParams, market: MemberParams, in_need: bool, history,
           w=None, my_r_borrow=None, my_r_save=None, obs_sd=0.02) -> Advice:
    """market: everyone's settings. my_r_*: your own outside rates, if different."""
    N, pot = chit.n_members, chit.pot
    t = len(history) + 1
    if not 1 <= t <= N - 2:
        raise ValueError(f"advice is for months 1..{N - 2}; got month {t}")
    for d in history:
        if not chit.commission <= d <= chit.bid_cap:
            raise ValueError(f"discount {d} is outside [commission, bid_cap]")
    w = eq.solve(chit, market).w if w is None else w
    me = replace(market,
                 r_borrow=market.r_borrow if my_r_borrow is None else my_r_borrow,
                 r_save=market.r_save if my_r_save is None else my_r_save)
    mine = eq.backward(chit, me, w, respond=True)

    # Belief about K (everyone waiting, you included), then about k (the others)
    # given your own need: P(k) is proportional to P(K = k + h) x P(you're in
    # that state | K), since members are interchangeable.
    belief = needy_belief(chit, market, w, history, obs_sd)
    nw, h = N - t, int(in_need)
    n = nw - 1
    pk = np.array([belief[k + h] * ((k + h) / nw if h else (nw - k) / nw)
                   for k in range(n + 1)])
    pk /= pk.sum()

    limit = float(pk @ mine.x[t, h, : n + 1])
    p_win = price_sum = 0.0
    for k, q in enumerate(pk):
        rivals = eq._groups(w, t, k, n - k, k + h)
        for qo, lab, d in eq.auction(chit, [("me", limit, 1)] + rivals):
            if lab == "me":
                p_win += q * qo
                price_sum += q * qo * d
    expected_price = price_sum / p_win if p_win > 0 else float("nan")
    value = float(pk @ mine.V[t, h, : n + 1]) * pot

    if p_win < 0.05:
        msg = (f"Your limit is {limit:.1%} of the pot, but others will probably "
               f"outbid you this month. Waiting costs you little.")
    else:
        msg = (f"Bid up to {limit:.1%} of the pot ({limit * pot:,.0f} off a pot of "
               f"{pot:,.0f}). Chance of winning this month: about {p_win:.0%}, "
               f"at an expected discount of {expected_price:.1%}.")
    return Advice(t, limit, limit * pot, p_win, expected_price, value, belief, msg)
