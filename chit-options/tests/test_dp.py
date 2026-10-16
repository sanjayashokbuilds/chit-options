import itertools

import numpy as np
import pytest

from chit import dp
from chit.mechanics import ChitParams
from chit.members import MemberParams, myopic_strategy
from chit.simulate import member_pv, simulate_many

MEMBERS = MemberParams(r_borrow=0.03, r_save=0.005, p_need=0.15)


def test_dp_beats_every_possible_policy_in_a_tiny_chit():
    # N = 4: decisions in months 1-2, ten (t, h, k) states, 2^10 = 1,024 policies.
    chit = ChitParams(4, 100, 0.05, 0.40)
    best = dp.solve(chit, MEMBERS).value
    states = [(t, h, k) for t in (1, 2) for h in (0, 1) for k in range(4 - t)]
    values = []
    for choice in itertools.product([False, True], repeat=len(states)):
        policy = np.zeros((4, 2, 4), dtype=bool)
        for s, c in zip(states, choice):
            policy[s] = c
        values.append(dp.evaluate_policy(chit, MEMBERS, policy))
    assert best == pytest.approx(max(values))


def test_dp_beats_simple_rules():
    chit = ChitParams(10, 100, 0.05, 0.40)
    r = dp.solve(chit, MEMBERS)
    never = dp.evaluate_policy(chit, MEMBERS, np.zeros_like(r.bid))
    always = dp.evaluate_policy(chit, MEMBERS, np.ones_like(r.bid))
    assert r.value >= never and r.value >= always


def test_dp_value_matches_the_simulator():
    # Independent check of the DP's transition maths: play the DP's policy in
    # the ordinary month-by-month simulator and average the realised values.
    chit = ChitParams(6, 100, 0.05, 0.40)
    r = dp.solve(chit, MEMBERS)
    policy = lambda t, h, k: bool(r.bid[t, h, k])
    paths = simulate_many(chit, MEMBERS, myopic_strategy(chit, MEMBERS), 10_000,
                          seed=11, focal=(1, policy))
    pv = np.array([member_pv(chit, MEMBERS, p, 1) for p in paths])
    se = pv.std() / np.sqrt(len(pv))
    assert abs(pv.mean() - r.value) < 4 * se


def test_dp_needs_the_foreman_month():
    with pytest.raises(ValueError):
        dp.solve(ChitParams(5, 100, foreman_first=False), MEMBERS)
