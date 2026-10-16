import numpy as np
import pytest

from chit import dp
from chit import equilibrium as eq
from chit.mechanics import ChitParams
from chit.members import MemberParams
from chit.simulate import member_pv, simulate_many

CHIT = ChitParams(8, 100, 0.05, 0.40)
MEMBERS = MemberParams(r_borrow=0.02, r_save=0.005, p_need=0.10)


def test_auction_rules():
    c = ChitParams(10, 100, 0.05, 0.40)
    # one clear top bidder pays the second-highest willingness
    assert eq.auction(c, [("me", 0.3, 1), ("needy", 0.2, 2)]) == [(1.0, "me", 0.2)]
    # a tie at the top: lottery, price = the tied willingness
    out = eq.auction(c, [("me", 0.4, 1), ("needy", 0.4, 3), ("fine", 0.1, 2)])
    assert out == [(0.25, "me", 0.4), (0.75, "needy", 0.4)]
    # a lone bidder pays the minimum
    assert eq.auction(c, [("me", 0.3, 1)]) == [(1.0, "me", 0.05)]


def test_equilibrium_converges_with_no_profitable_deviation():
    e = eq.solve(CHIT, MEMBERS)
    assert e.converged
    assert abs(e.deviation_gain) < 1e-8


def test_same_equilibrium_from_different_starting_tables():
    base = eq.solve(CHIT, MEMBERS).w
    mask = eq.valid_mask(CHIT.n_members)
    for start_value in (CHIT.commission, CHIT.bid_cap):
        start = np.full_like(base, start_value)
        start[CHIT.n_members - 1, :, 0] = CHIT.commission
        other = eq.solve(CHIT, MEMBERS, start=start).w
        assert np.max(np.abs(other[mask] - base[mask])) < 1e-8


def test_best_response_to_myopic_rivals_is_at_least_the_dp_value():
    # Choosing any willingness includes the DP's two choices (cap or sit out)
    # as special cases, so it can't be worth less.
    br = eq.backward(CHIT, MEMBERS, eq.myopic_table(CHIT, MEMBERS), respond=True).value
    assert br >= dp.solve(CHIT, MEMBERS).value - 1e-12


def test_equilibrium_value_matches_the_simulator():
    e = eq.solve(CHIT, MEMBERS)
    paths = simulate_many(CHIT, MEMBERS, eq.TableStrategy(e.w), 8_000, seed=4)
    pv = np.array([member_pv(CHIT, MEMBERS, p, 3) for p in paths])
    assert abs(pv.mean() - e.value) < 4 * pv.std() / np.sqrt(len(pv))
