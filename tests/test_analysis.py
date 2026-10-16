from dataclasses import replace

import numpy as np
import pytest

from chit import analysis as an
from chit import equilibrium as eq
from chit.implied import forward_rates
from chit.mechanics import ChitParams
from chit.members import MemberParams
from chit.simulate import simulate_many

CHIT = ChitParams(8, 100, 0.05, 0.40)
MEMBERS = MemberParams(r_borrow=0.02, r_save=0.005, p_need=0.10)


def test_exact_term_structure_matches_simulation():
    e = eq.solve(CHIT, MEMBERS)
    ts = an.term_structure(CHIT, MEMBERS, e.w)
    paths = simulate_many(CHIT, MEMBERS, eq.TableStrategy(e.w), 8_000, seed=7)
    D = np.array([p.discounts for p in paths])
    F = np.array([forward_rates(CHIT, p.discounts) for p in paths])[:, 1:]
    n = len(paths)
    assert np.all(np.abs(D.mean(0) - ts.discount) <= 4 * D.std(0) / np.sqrt(n) + 1e-12)
    assert np.all(np.abs(F.mean(0) - ts.forward[1:]) <= 4 * F.std(0) / np.sqrt(n) + 1e-12)


def test_last_month_discount_is_the_commission():
    ts = an.term_structure(CHIT, MEMBERS, eq.solve(CHIT, MEMBERS).w)
    assert ts.discount[-1] == pytest.approx(CHIT.commission)


def test_tighter_cap_lowers_implied_rates_when_it_binds():
    # High-demand setting where early discounts exceed 30% without a cap.
    chit = ChitParams(20, 100, 0.05, 0.40)
    m = MemberParams(r_borrow=0.04, r_save=0.005, p_need=0.20)
    loose, _, _ = an.run(chit, m)
    tight, ts, _ = an.run(replace(chit, bid_cap=0.30), m)
    assert ts.p_cap[1] > 0.5                       # the cap really binds
    assert tight.mean_forward < loose.mean_forward
    assert tight.mean_yield < loose.mean_yield
