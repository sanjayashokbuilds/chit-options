import numpy as np
import pytest

from chit.mechanics import ChitParams, cash_flow_matrix, settle_month
from chit.rates import annualise, irr_roots, monthly_irr, npv


def test_worked_example_from_notes():
    # 10 members x £100, month-2 winner bids 30%, commission 5%
    p = ChitParams(n_members=10, instalment=100, commission=0.05)
    payout, payment, commission = settle_month(p, 0.30)
    assert payout == pytest.approx(700)
    assert commission == pytest.approx(50)
    assert payment == pytest.approx(75)   # 100 - (300 - 50) / 10


def test_money_is_conserved():
    # Everything members pay in either goes back out as a pot or to the foreman.
    p = ChitParams(n_members=6, instalment=50, commission=0.05)
    flows, commissions = cash_flow_matrix(
        p, winners=[0, 3, 1, 5, 2, 4], discounts=[0, 0.35, 0.25, 0.15, 0.08, 0.05]
    )
    assert flows.sum() + commissions.sum() == pytest.approx(0)


def test_no_discount_no_commission_means_zero_interest():
    # If nobody gives anything up, every member gets back exactly what they paid.
    p = ChitParams(n_members=5, instalment=10, commission=0.0)
    flows, _ = cash_flow_matrix(p, winners=[0, 1, 2, 3, 4], discounts=[0] * 5)
    assert np.allclose(flows.sum(axis=1), 0)
    for row in flows[1:-1]:   # middle members: rate is exactly zero
        assert monthly_irr(row) == pytest.approx(0, abs=1e-9)


def test_early_winners_borrow_late_winners_save():
    p = ChitParams(n_members=6, instalment=50, commission=0.05)
    flows, _ = cash_flow_matrix(
        p, winners=[0, 1, 2, 3, 4, 5], discounts=[0, 0.35, 0.25, 0.15, 0.08, 0.05]
    )
    month1_winner, last_winner = flows[1], flows[5]
    # Month-1 winner: receives a lot early, so their IRR is a borrowing COST.
    # Last winner: pays in first, receives last, so their IRR is a saving RETURN.
    assert month1_winner[1] > 0 and last_winner[:5].max() < 0
    assert monthly_irr(month1_winner) > 0
    assert monthly_irr(last_winner) > 0


def test_bid_outside_rules_is_rejected():
    p = ChitParams(n_members=10, instalment=100, commission=0.05, bid_cap=0.40)
    with pytest.raises(ValueError):
        settle_month(p, 0.41)   # above cap
    with pytest.raises(ValueError):
        settle_month(p, 0.04)   # below commission: dividend would be negative


def test_irr_of_simple_loan():
    # Borrow 100 now, repay 110 next month: 10% a month.
    assert monthly_irr([100, -110]) == pytest.approx(0.10)
    assert annualise(0.01) == pytest.approx(1.01**12 - 1)


def test_irr_finds_multiple_roots():
    # Flows +1, -5, +6 have NPV = 0 at r = 1 and r = 2 (x = 1/(1+r) solves 6x^2-5x+1=0).
    roots = irr_roots([1, -5, 6], lo=0.5, hi=2.5)
    assert roots == pytest.approx([1.0, 2.0], abs=1e-6)
    assert npv(1.0, [1, -5, 6]) == pytest.approx(0)
