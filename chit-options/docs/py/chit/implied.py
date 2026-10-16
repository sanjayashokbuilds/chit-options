"""Interest rates implied by each month's winning bid (the chit's term structure).

KEY FACT these rest on: in month s EVERY member pays the same amount
(instalment minus dividend), whether or not they have already won. So for one
member, "win in month t" versus "win in month u" (holding the discount path
fixed) differs ONLY in the payout: pot*(1 - d_t) at t versus pot*(1 - d_u) at u.

That means the fraction of the pot a winner keeps, 1 - d_t, works like the
price of a zero-coupon bond: the market's price for getting the pot in month t.
Reading rates off those prices is exactly reading a yield curve off bond prices.

Three rates per month t:
- forward_rates: the price of moving your pot one month earlier, t+1 -> t.
- yields_to_end: the average monthly rate from month t to the last month.
- loan_rates: the winner's cost of the remaining "loan" (receive at t, repay
  after), the per-winner style used by Klonner & Rai. Ignores what the winner
  paid BEFORE t, so late winners (net savers) can show negative rates.

All three are NaN where no auction sets the price (the foreman's month), and
the last two are NaN in the last month (nothing comes after it).
"""

import numpy as np

from .mechanics import ChitParams, monthly_settlements
from .rates import monthly_irr


def _prices(params: ChitParams, discounts) -> np.ndarray:
    """Fraction of the pot each month's winner keeps; NaN for the foreman's month."""
    monthly_settlements(params, discounts)  # validates every bid against the rules
    price = 1 - np.asarray(discounts, dtype=float)
    if params.foreman_first:
        price[0] = np.nan
    return price


def forward_rates(params: ChitParams, discounts) -> np.ndarray:
    """f[t] solves price[t] * (1 + f[t]) = price[t+1]. Length N - 1."""
    price = _prices(params, discounts)
    return price[1:] / price[:-1] - 1


def yields_to_end(params: ChitParams, discounts) -> np.ndarray:
    """y[t] solves price[t] * (1 + y[t])**(months left) = price[last]. Length N."""
    price = _prices(params, discounts)
    n = params.n_members
    months_left = np.arange(n - 1, 0, -1)                 # N-1, ..., 1
    y = np.full(n, np.nan)                                # last month stays NaN
    y[:-1] = (price[-1] / price[:-1]) ** (1 / months_left) - 1
    return y


def loan_rates(params: ChitParams, discounts) -> np.ndarray:
    """IRR of: receive (payout - payment) at t, then pay each later month's payment."""
    payouts, payments, _ = monthly_settlements(params, discounts)
    n = params.n_members
    rates = np.full(n, np.nan)
    for t in range(n - 1):
        if t == 0 and params.foreman_first:
            continue
        flows = np.concatenate([[payouts[t] - payments[t]], -payments[t + 1:]])
        # One sign change (+ then all -), so the root is unique; wide range
        # because late winners repay little and get very negative rates.
        rates[t] = monthly_irr(flows, lo=-0.999, hi=3.0)
    return rates
