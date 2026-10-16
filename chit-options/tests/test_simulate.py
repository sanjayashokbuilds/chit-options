import numpy as np
import pytest

from chit.mechanics import ChitParams, cash_flow_matrix
from chit.members import MemberParams, lottery_strategy, myopic_reservation, myopic_strategy
from chit.simulate import run_auction, simulate_many

CHIT = ChitParams(n_members=10, instalment=100, commission=0.05, bid_cap=0.40)
MEMBERS = MemberParams(r_borrow=0.02, r_save=0.005, p_need=0.10)


def test_reservation_by_hand():
    # Month 2 of 10, in need: k = 7 months to the end, rate 2%.
    expected = 1 - 0.95 / 1.02**7
    assert myopic_reservation(CHIT, MEMBERS, 2, True) == pytest.approx(expected)


def test_reservation_rises_with_need_and_time_left():
    early_need = myopic_reservation(CHIT, MEMBERS, 1, True)
    early_fine = myopic_reservation(CHIT, MEMBERS, 1, False)
    late_need = myopic_reservation(CHIT, MEMBERS, 8, True)
    assert early_need > early_fine and early_need > late_need
    assert myopic_reservation(CHIT, MEMBERS, 9, True) == pytest.approx(0.05)  # floor


def test_english_pays_second_highest_sealed_pays_highest():
    rng = np.random.default_rng(0)
    assert run_auction(rng, [1, 2, 3], [0.30, 0.20, 0.10], CHIT, "english") == (1, 0.20)
    assert run_auction(rng, [1, 2, 3], [0.30, 0.20, 0.10], CHIT, "sealed") == (1, 0.30)


def test_ties_at_the_cap_go_to_lottery():
    rng = np.random.default_rng(0)
    results = {run_auction(rng, [4, 7], [0.9, 0.5], CHIT) for _ in range(50)}
    assert results == {(4, 0.40), (7, 0.40)}   # both clipped to the cap, both can win


def test_every_simulated_chit_follows_the_rules():
    for path in simulate_many(CHIT, MEMBERS, myopic_strategy(CHIT, MEMBERS), 200):
        assert path.winners[0] == 0 and sorted(path.winners) == list(range(10))
        assert np.all((path.discounts[1:] >= 0.05) & (path.discounts[1:] <= 0.40))
        flows, commissions = cash_flow_matrix(CHIT, path.winners, path.discounts)
        assert flows.sum() + commissions.sum() == pytest.approx(0)


def test_needs_last_until_the_member_wins():
    for path in simulate_many(CHIT, MEMBERS, myopic_strategy(CHIT, MEMBERS), 100):
        for i in range(10):
            win_month = int(np.flatnonzero(path.winners == i)[0])
            before = path.needs[i, : win_month + 1].astype(int)
            assert np.all(np.diff(before) >= 0)   # never goes from needy back to fine


def test_lottery_strategy_is_a_fair_random_rosca():
    paths = simulate_many(CHIT, MEMBERS, lottery_strategy(CHIT), 4000, seed=1)
    assert all(np.allclose(p.discounts[1:], 0.05) for p in paths)
    month1 = np.bincount([p.winners[1] for p in paths], minlength=10)[1:]
    assert month1.min() > 4000 / 9 * 0.8   # each of 9 bidders wins month 1 ~1/9 of the time


def test_more_emergencies_mean_higher_early_discounts():
    def mean_month1_discount(p_need):
        m = MemberParams(r_borrow=0.02, r_save=0.005, p_need=p_need)
        paths = simulate_many(CHIT, m, myopic_strategy(CHIT, m), 2000, seed=2)
        return np.mean([p.discounts[1] for p in paths])
    assert mean_month1_discount(0.30) > mean_month1_discount(0.05)
