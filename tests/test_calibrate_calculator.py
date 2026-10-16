import numpy as np
import pytest

from chit import analysis as an
from chit import calculator as calc
from chit import calibrate as cal
from chit import equilibrium as eq
from chit.mechanics import ChitParams
from chit.members import MemberParams
from chit.simulate import simulate_many

CHIT = ChitParams(12, 100, 0.05, 0.60)
TRUE = MemberParams(r_borrow=0.06, r_save=cal.R_SAVE, p_need=0.10)


def test_calibration_recovers_known_settings_from_their_own_moments():
    # Identification check: fake "data" from known settings, then fit.
    m = cal.model_moments(CHIT, TRUE, threshold=0.12)
    targets = {"early_mean": m.early_mean, "early_share_above": m.early_share_above}
    fits = cal.grid_search(CHIT, [0.05, 0.10, 0.20], [0.03, 0.06], targets=targets,
                           threshold=0.12)
    assert (fits[0].p_need, fits[0].r_borrow) == (0.10, 0.06)
    assert fits[0].loss < 1e-12 < fits[1].loss


def test_belief_with_no_history_is_the_prior():
    w = eq.solve(CHIT, TRUE).w
    b = calc.needy_belief(CHIT, TRUE, w, [])
    assert np.allclose(b, an.month1_prior(CHIT, TRUE)) and b.sum() == pytest.approx(1)


def test_past_bids_reveal_how_many_are_in_need():
    # On simulated chits, the filter should put more probability on the TRUE
    # number in need than the no-information forecast does.
    chit, m = ChitParams(10, 100, 0.05, 0.40), MemberParams(0.03, 0.005, 0.15)
    w = eq.solve(chit, m).w
    t = 5
    prior_t = an.term_structure(chit, m, w).laws[t][0]
    gain = []
    for path in simulate_many(chit, m, eq.TableStrategy(w), 300, seed=3):
        waiting = ~np.isin(np.arange(10), path.winners[:t])
        true_K = int(path.needs[waiting, t].sum())
        belief = calc.needy_belief(chit, m, w, path.discounts[1:t], obs_sd=0.005)
        gain.append(belief[true_K] - prior_t[true_K])
    assert np.mean(gain) > 0.05


def test_advice_makes_sense():
    chit, m = ChitParams(20, 100, 0.05, 0.40), MemberParams(0.02, 0.005, 0.10)
    w = eq.solve(chit, m).w
    history = [0.19, 0.19, 0.18]
    fine = calc.advise(chit, m, False, history, w=w)
    needy = calc.advise(chit, m, True, history, w=w)
    desperate = calc.advise(chit, m, True, history, w=w, my_r_borrow=0.06)
    assert chit.commission <= fine.limit <= chit.bid_cap
    assert needy.limit > fine.limit and desperate.limit > needy.limit
    assert 0 <= needy.p_win <= 1
    with pytest.raises(ValueError):
        calc.advise(chit, m, True, [0.9], w=w)       # bid above the cap
