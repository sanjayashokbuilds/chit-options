"""Build the data and Python files the web app (docs/) needs.

Run from the repo root:  python scripts/build_site.py   (about 10 minutes)

docs/ is served as-is by GitHub Pages. This script writes:
  docs/data/explore.json    term structures for a grid of settings
  docs/data/example.json    one simulated 20-member chit, month by month
  docs/data/tables.json     equilibrium bidding tables for the calculator
  docs/data/game.json       the equilibrium the game's rivals follow
  docs/py/chit/*.py         a copy of the package, loaded into Pyodide
"""

import itertools
import json
import shutil
from dataclasses import replace
from pathlib import Path

import numpy as np

from chit import analysis as an
from chit import calibrate as cal
from chit import equilibrium as eq
from chit.mechanics import ChitParams, monthly_settlements
from chit.members import MemberParams
from chit.simulate import simulate_chit
from chit.web import table_to_lists

DOCS = Path("docs")
FIT = MemberParams(r_borrow=0.033, r_save=cal.R_SAVE, p_need=0.0425)   # from run_calibration.py
COMMISSION = 0.05
NO_CAP = 0.60          # never binds in these settings


def r(x, nd=5):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def explore():
    grid = {"members": [20, 30, 40], "p_need": [0.02, 0.0425, 0.10, 0.20],
            "r_borrow": [0.01, 0.02, 0.033, 0.05], "cap": [0.30, 0.40, NO_CAP]}
    out = {"grid": grid, "commission": COMMISSION, "r_save": cal.R_SAVE, "scenarios": {}}
    for n, p, rb, cap in itertools.product(*grid.values()):
        chit = ChitParams(n, 100, COMMISSION, cap)
        m = MemberParams(r_borrow=rb, r_save=cal.R_SAVE, p_need=p)
        sc, ts, e = an.run(chit, m)
        # A handful of settings end in a tiny cycle (table moves ~1e-6) caused by
        # near-ties; we accept them only if nobody can gain by deviating.
        assert abs(e.deviation_gain) < 1e-8 and e.changes[-1] < 1e-5, (n, p, rb, cap)
        out["scenarios"][f"{n}|{p}|{rb}|{cap}"] = {
            "yield": [r(v) for v in an.annual(ts.yield_end[1:-1])],
            "forward": [r(v) for v in an.annual(ts.forward[1:])],
            "discount": [r(v) for v in ts.discount[1:-1]],
            "needy_share": [r(v) for v in ts.needy_share[1:-1]],
            "p_cap": [r(v) for v in ts.p_cap[1:-1]],
            "mean_yield": r(sc.mean_yield), "mean_forward": r(sc.mean_forward),
            "yield_peak_month": ts.peak_month("yield"),
            "forward_peak_month": ts.peak_month("forward"),
            "seat_value": r(sc.seat_value),
            "converged": bool(e.converged), "last_change": float(e.changes[-1]),
        }
        print("explore", n, p, rb, cap)
    return out


def example(seed=7, n=20, instalment=500):
    """One equilibrium chit, chosen so the story has a few needy members."""
    chit = ChitParams(n, instalment, COMMISSION, 0.40)
    w = eq.solve(chit, FIT).w
    path = simulate_chit(np.random.default_rng(seed), chit, FIT, eq.TableStrategy(w))
    payouts, payments, commissions = monthly_settlements(chit, path.discounts)
    months = []
    for t in range(n):
        waiting = [i for i in range(n) if i not in path.winners[:t]]
        months.append({
            "winner": int(path.winners[t]), "discount": r(path.discounts[t]),
            "payout": r(payouts[t], 2), "payment": r(payments[t], 2),
            "commission": r(commissions[t], 2),
            "waiting": waiting,
            "in_need": [i for i in waiting if path.needs[i, t]],
        })
    return {"members": n, "instalment": instalment, "pot": chit.pot,
            "commission": COMMISSION, "cap": 0.40, "months": months}


def tables():
    out = {"market": {"p_need": FIT.p_need, "r_borrow": FIT.r_borrow, "r_save": FIT.r_save,
                      "commission": COMMISSION}, "tables": {}}
    for n, cap in itertools.product([20, 25, 30, 40], [0.30, 0.40]):
        e = eq.solve(ChitParams(n, 100, COMMISSION, cap), FIT)
        assert e.converged and abs(e.deviation_gain) < 1e-8
        out["tables"][f"{n}|{cap}"] = table_to_lists(e.w)
        print("table", n, cap)
    return out


def game():
    """The equilibrium the 'Play a chit' game's rivals follow: a short, lively
    10-member chit (needs more common than the calibrated 4.25% so the game
    has some drama)."""
    chit = ChitParams(10, 1000, COMMISSION, 0.40)
    m = MemberParams(r_borrow=FIT.r_borrow, r_save=FIT.r_save, p_need=0.12)
    e = eq.solve(chit, m)
    assert e.converged and abs(e.deviation_gain) < 1e-8
    return {"members": 10, "instalment": 1000, "commission": COMMISSION, "cap": 0.40,
            "p_need": m.p_need, "r_borrow": m.r_borrow, "r_save": m.r_save,
            "table": table_to_lists(e.w)}


def main():
    (DOCS / "data").mkdir(parents=True, exist_ok=True)
    py = DOCS / "py" / "chit"
    if py.exists():
        shutil.rmtree(py)
    py.mkdir(parents=True)
    for f in Path("chit").glob("*.py"):
        shutil.copy(f, py / f.name)
    (DOCS / "py" / "files.json").write_text(json.dumps(sorted(f.name for f in py.glob("*.py"))))

    (DOCS / "data" / "game.json").write_text(json.dumps(game()))
    (DOCS / "data" / "example.json").write_text(json.dumps(example()))
    (DOCS / "data" / "tables.json").write_text(json.dumps(tables()))
    (DOCS / "data" / "explore.json").write_text(json.dumps(explore()))
    print("done")


if __name__ == "__main__":
    main()
