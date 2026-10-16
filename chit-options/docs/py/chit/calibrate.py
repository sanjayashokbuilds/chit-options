"""Calibrate the two unobservable settings to published chit-company figures.

We can't see members' cash needs or outside borrowing rates, so we choose
p_need (how often needs arrive) and r_borrow (what outside credit costs) to make
the equilibrium reproduce bid statistics published by Klonner & Rai, then check
the model against a figure we did NOT target.

Data (Klonner & Rai, chit company in Tamil Nadu; most common group:
40 members, 40 months, Rs 250 a month, Rs 10,000 pot; commission 5-6%;
oral ascending auctions; lottery among bidders tied at the cap):
  Before the 1993 cap (no binding limit):
    TARGET 1: early winners' average bid = 35.07% of the pot
    TARGET 2: 79.1% of first-half winning bids were >= 30% of the pot
  After the 1993 cap of 30% (NOT targeted, used as an out-of-sample check):
    72% of first-half winning bids were at the 30% cap

Our reading of the data (flagged in the README):
- "first half" and "early" = auctions in rounds 2-20 (our months 1-19);
  round 1 is the foreman's.
- "no binding limit" before 1993 is modelled as a 60% cap, which never binds here.
- Saving rate fixed at 9% a year (about 0.72% a month), the bank deposit rate
  in the study summarised in the project brief.
- Commission 5% (the bottom of the reported 5-6%).
"""

from dataclasses import dataclass, replace

import numpy as np

from . import analysis as an
from . import equilibrium as eq
from .mechanics import ChitParams
from .members import MemberParams

KR_CHIT = ChitParams(n_members=40, instalment=250, commission=0.05, bid_cap=0.60)
KR_CAP = 0.30
R_SAVE = 1.09 ** (1 / 12) - 1
TARGETS = {"early_mean": 0.3507, "early_share_above": 0.791}
THRESHOLD = 0.30
CHECK_POST_CAP_AT_CAP = 0.72


@dataclass
class Moments:
    early_mean: float         # mean winning discount, months 1-19
    early_share_above: float  # share of months 1-19 auctions with discount >= threshold


def early_months(chit: ChitParams):
    return range(1, chit.n_members // 2)


def model_moments(chit: ChitParams, members: MemberParams, threshold=THRESHOLD) -> Moments:
    e = eq.solve(chit, members)
    ts = an.term_structure(chit, members, e.w)
    months = early_months(chit)
    return Moments(ts.mean_discount(months), ts.share_at_least(threshold, months))


def loss(m: Moments, targets=TARGETS) -> float:
    """Sum of squared relative errors (relative to at least 0.01, so a zero
    target doesn't divide by zero)."""
    return sum(((getattr(m, k) - v) / max(abs(v), 0.01)) ** 2 for k, v in targets.items())


@dataclass
class Fit:
    p_need: float
    r_borrow: float
    moments: Moments
    loss: float


def grid_search(chit, p_values, r_values, r_save=R_SAVE, targets=TARGETS, threshold=THRESHOLD):
    """Solve the equilibrium at every (p_need, r_borrow) pair; best fit first."""
    fits = []
    for p in p_values:
        for r in r_values:
            m = model_moments(chit, MemberParams(r_borrow=r, r_save=r_save, p_need=p), threshold)
            fits.append(Fit(p, r, m, loss(m, targets)))
    return sorted(fits, key=lambda f: f.loss)


def post_cap_check(chit, fit: Fit, r_save=R_SAVE, cap=KR_CAP):
    """With the fitted settings and a 30% cap: share of early auctions AT the cap."""
    capped = replace(chit, bid_cap=cap)
    members = MemberParams(r_borrow=fit.r_borrow, r_save=r_save, p_need=fit.p_need)
    e = eq.solve(capped, members)
    ts = an.term_structure(capped, members, e.w)
    return ts.share_at_least(cap, early_months(capped)), ts
