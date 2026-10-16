import numpy as np

from chit import dp, lsm
from chit.mechanics import ChitParams
from chit.members import MemberParams

CHIT = ChitParams(10, 100, 0.05, 0.40)
MEMBERS = MemberParams(r_borrow=0.02, r_save=0.005, p_need=0.10)


def test_lsm_paths_follow_the_same_rules_as_the_dp():
    # Play the DP's own policy on LSM's simulated paths: same value, within noise.
    d = dp.solve(CHIT, MEMBERS)
    mean, se = lsm.evaluate_table(CHIT, MEMBERS, d.bid, n_paths=100_000, seed=5)
    assert abs(mean - d.value) < 4 * se


def test_lsm_learns_the_dp_value():
    d = dp.solve(CHIT, MEMBERS)
    r = lsm.solve(CHIT, MEMBERS, n_paths=40_000, kind="indicator", seed=1)
    assert abs(r.value - d.value) < 4 * r.se


def test_lsm_never_beats_the_dp_by_more_than_noise():
    # The DP is optimal, so any learned rule is worth at most the DP value.
    for seed in range(3):
        r = lsm.solve(CHIT, MEMBERS, n_paths=20_000, kind="poly", seed=seed)
        assert r.value < dp.solve(CHIT, MEMBERS).value + 4 * r.se


def test_learned_rule_matches_dp_where_states_are_common():
    # With no needy rival (k = 0) the state occurs on most paths early on.
    d = dp.solve(CHIT, MEMBERS)
    r = lsm.solve(CHIT, MEMBERS, n_paths=40_000, kind="indicator", seed=2)
    table = lsm.policy_table(CHIT, r, "indicator")
    assert np.array_equal(table[1:5, :, 0], d.bid[1:5, :, 0])
