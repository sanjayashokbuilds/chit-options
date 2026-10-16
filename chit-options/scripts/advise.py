"""Command-line bidding advice.

Example (a 40-member chit, Rs 250 a month, 3 auctions so far, you're in need):
    python scripts/advise.py --members 40 --instalment 250 --history 0.35,0.34,0.33 --in-need

Market settings (how often needs arrive, outside borrowing rate) default to the
calibrated values in results/calibration.json if it exists.
"""

import argparse
import json
from pathlib import Path

from chit import calculator as calc
from chit import calibrate as cal
from chit.mechanics import ChitParams
from chit.members import MemberParams


def main():
    fit = {"p_need": 0.05, "r_borrow": 0.03}
    path = Path("results/calibration.json")
    if path.exists():
        fit = json.loads(path.read_text())["fit"]

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--members", type=int, default=40)
    ap.add_argument("--instalment", type=float, default=250)
    ap.add_argument("--commission", type=float, default=0.05)
    ap.add_argument("--cap", type=float, default=0.40)
    ap.add_argument("--history", default="", help="winning discounts so far, e.g. 0.35,0.34")
    ap.add_argument("--in-need", action="store_true")
    ap.add_argument("--p-need", type=float, default=fit["p_need"])
    ap.add_argument("--market-borrow", type=float, default=fit["r_borrow"], help="monthly")
    ap.add_argument("--my-borrow", type=float, default=None, help="your own monthly borrowing rate")
    a = ap.parse_args()

    chit = ChitParams(a.members, a.instalment, a.commission, a.cap)
    market = MemberParams(r_borrow=a.market_borrow, r_save=cal.R_SAVE, p_need=a.p_need)
    history = [float(x) for x in a.history.split(",") if x.strip()]
    advice = calc.advise(chit, market, a.in_need, history, my_r_borrow=a.my_borrow)
    print(f"Month {advice.month + 1} of {a.members} (auction {advice.month} after the foreman's month)")
    print(advice.message)
    print(f"Value of your remaining position today: {advice.position_value:,.0f}")


if __name__ == "__main__":
    main()
