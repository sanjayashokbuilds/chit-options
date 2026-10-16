import json

import numpy as np
import pytest

from chit import calculator as calc
from chit import equilibrium as eq
from chit.mechanics import ChitParams
from chit.members import MemberParams
from chit.web import advise_json, table_from_lists, table_to_lists


def test_table_survives_the_round_trip_to_json():
    w = eq.solve(ChitParams(8, 100, 0.05, 0.40), MemberParams(0.03, 0.005, 0.1)).w
    back = table_from_lists(json.loads(json.dumps(table_to_lists(w))))
    assert np.array_equal(np.isnan(back), np.isnan(w))
    assert np.allclose(back[~np.isnan(w)], w[~np.isnan(w)], atol=1e-8)


def test_browser_entry_point_matches_the_calculator():
    chit, m = ChitParams(12, 250, 0.05, 0.40), MemberParams(0.033, 0.0072, 0.0425)
    w = eq.solve(chit, m).w
    req = {"members": 12, "instalment": 250, "commission": 0.05, "cap": 0.40,
           "r_borrow": 0.033, "r_save": 0.0072, "p_need": 0.0425, "in_need": True,
           "history": [0.2, 0.19], "my_r_borrow": None, "table": table_to_lists(w)}
    got = json.loads(advise_json(json.dumps(req)))
    want = calc.advise(chit, m, True, [0.2, 0.19], w=w)
    assert got["limit"] == pytest.approx(want.limit, abs=1e-7)
    assert got["p_win"] == pytest.approx(want.p_win, abs=1e-7)
    assert got["month"] == 3 and len(got["belief"]) == 12 - 3 + 1
