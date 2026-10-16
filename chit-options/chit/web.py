"""Entry point for the web app, which runs this package in the browser (Pyodide).

JSON in, JSON out, so the JavaScript side never touches Python objects.
The equilibrium table is precomputed (scripts/build_site.py) and sent in with
the request, because solving it live in a browser takes too long.
"""

import json

import numpy as np

from . import calculator as calc
from .mechanics import ChitParams
from .members import MemberParams


def table_from_lists(rows) -> np.ndarray:
    """Nested lists with None for 'no such state' -> float array with NaN."""
    return np.array([[[np.nan if v is None else v for v in k_row] for k_row in h_rows]
                     for h_rows in rows], dtype=float)


def table_to_lists(w: np.ndarray):
    return [[[None if np.isnan(v) else round(float(v), 8) for v in k_row] for k_row in h_rows]
            for h_rows in w]


def advise_json(request: str) -> str:
    r = json.loads(request)
    chit = ChitParams(int(r["members"]), float(r["instalment"]), float(r["commission"]),
                      float(r["cap"]))
    market = MemberParams(r_borrow=float(r["r_borrow"]), r_save=float(r["r_save"]),
                          p_need=float(r["p_need"]))
    my_r = r.get("my_r_borrow")
    advice = calc.advise(chit, market, bool(r["in_need"]), [float(d) for d in r["history"]],
                         w=table_from_lists(r["table"]),
                         my_r_borrow=None if my_r is None else float(my_r))
    return json.dumps({
        "month": advice.month,
        "limit": advice.limit,
        "limit_amount": advice.limit_amount,
        "p_win": advice.p_win,
        "expected_price": None if np.isnan(advice.expected_price) else advice.expected_price,
        "position_value": advice.position_value,
        "belief": [float(b) for b in advice.belief],
        "message": advice.message,
    })
