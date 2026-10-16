import numpy as np
import pytest

from chit.implied import forward_rates, loan_rates, yields_to_end
from chit.mechanics import ChitParams, cash_flow_matrix

P10 = ChitParams(n_members=10, instalment=100, commission=0.05)
D10 = [0, 0.35, 0.30, 0.26, 0.22, 0.18, 0.14, 0.10, 0.07, 0.05]


def test_swapping_winning_months_only_changes_payouts():
    # The fact everything here rests on: payments don't depend on who has won.
    a, _ = cash_flow_matrix(P10, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], D10)
    b, _ = cash_flow_matrix(P10, [0, 2, 1, 3, 4, 5, 6, 7, 8, 9], D10)
    changed = np.argwhere(~np.isclose(a, b))
    assert {tuple(c) for c in changed} == {(1, 1), (1, 2), (2, 1), (2, 2)}


def test_forward_rate_by_hand():
    # Keep 70% in month 1 or 77% in month 2: waiting a month earns 77/70 - 1 = 10%.
    d = [0, 0.30, 0.23, 0.05]
    f = forward_rates(ChitParams(4, 100, 0.05), d)
    assert np.isnan(f[0])                    # foreman's month has no auction price
    assert f[1] == pytest.approx(0.77 / 0.70 - 1)


def test_yield_is_compounded_forwards():
    # Like spot vs forward rates for bonds: (1 + y_t)^k = product of the k forwards.
    f, y = forward_rates(P10, D10), yields_to_end(P10, D10)
    for t in range(1, 9):
        k = 9 - t
        assert (1 + y[t]) ** k == pytest.approx(np.prod(1 + f[t:]))
    assert np.isnan(y[0]) and np.isnan(y[-1])


def test_flat_discounts_mean_zero_forward_rates():
    f = forward_rates(P10, [0] + [0.05] * 9)
    assert np.allclose(f[1:], 0)


def test_loan_rate_by_hand():
    # N=3, m=100, no commission, no foreman. Month-0 winner bids 20%:
    # gets 240, pays 100 - 60/3 = 80, so net +160. Then pays 90 (month 1: 30/3
    # dividend) and 100 (month 2: no discount). Solve 160 = 90x + 100x^2, x = 1/(1+r).
    p = ChitParams(3, 100, commission=0.0, foreman_first=False)
    x = (-90 + np.sqrt(90**2 + 4 * 100 * 160)) / (2 * 100)
    assert loan_rates(p, [0.20, 0.10, 0.0])[0] == pytest.approx(1 / x - 1)


def test_loan_rate_goes_negative_for_late_winners():
    # Documents the limitation: late winners are net savers, so a "loan" view
    # from month t onwards shows them receiving more than they repay.
    r = loan_rates(P10, D10)
    assert r[1] > 0 and r[8] < 0
