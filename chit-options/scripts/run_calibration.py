"""Calibrate to Klonner & Rai's pre-1993 bid figures, then test the 1993 cap.

Run from the repo root:  python scripts/run_calibration.py   (a few minutes)
Writes results/calibration.json and results/calibrated_term_structure.png.
"""

import json
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from chit import analysis as an
from chit import calibrate as cal
from chit.members import MemberParams

OUT = Path("results")
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "axes.grid": True, "grid.color": "#e4e3df",
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "lines.linewidth": 2, "legend.frameon": False,
})


def summarise(chit, members, label):
    sc, ts, _ = an.run(chit, members, label)
    months = cal.early_months(chit)
    return {
        **{k: (round(v, 6) if isinstance(v, float) else v) for k, v in asdict(sc).items()},
        "early_mean_discount": round(ts.mean_discount(months), 4),
        "early_share_at_or_above_30": round(ts.share_at_least(0.30, months), 4),
        "late_mean_discount": round(ts.mean_discount(range(chit.n_members // 2, chit.n_members - 1)), 4),
    }, ts


def main():
    OUT.mkdir(exist_ok=True)
    chit = cal.KR_CHIT

    coarse = cal.grid_search(chit, [0.02, 0.05, 0.10, 0.15, 0.20, 0.30],
                             [0.02, 0.03, 0.04, 0.06, 0.08])
    best = coarse[0]
    fine = cal.grid_search(chit, [round(best.p_need * f, 4) for f in (0.7, 0.85, 1, 1.15, 1.3)],
                           [round(best.r_borrow * f, 4) for f in (0.8, 0.9, 1, 1.1, 1.2)])
    fit = fine[0]
    members = MemberParams(r_borrow=fit.r_borrow, r_save=cal.R_SAVE, p_need=fit.p_need)
    print("fit:", fit)

    before, ts_before = summarise(chit, members, "before 1993 (no binding cap)")
    after, ts_after = summarise(replace(chit, bid_cap=cal.KR_CAP), members, "after 1993 (30% cap)")
    at_cap, _ = cal.post_cap_check(chit, fit)

    out = {
        "data": {"source": "Klonner & Rai, chit company, 40-member / 40-month groups",
                 "targets": cal.TARGETS, "untargeted_post_cap_share_at_cap": cal.CHECK_POST_CAP_AT_CAP},
        "fixed": {"chit": asdict(chit), "r_save_monthly": round(cal.R_SAVE, 6)},
        "fit": {"p_need": fit.p_need, "r_borrow": fit.r_borrow,
                "r_borrow_annual": round((1 + fit.r_borrow) ** 12 - 1, 4),
                "moments": asdict(fit.moments), "loss": fit.loss},
        "coarse_top5": [{"p_need": f.p_need, "r_borrow": f.r_borrow, "loss": round(f.loss, 6),
                         **asdict(f.moments)} for f in coarse[:5]],
        "before_cap": before,
        "after_cap": after,
        "post_cap_check": {"model_share_at_cap": round(at_cap, 4),
                           "data_share_at_cap": cal.CHECK_POST_CAP_AT_CAP},
    }
    (OUT / "calibration.json").write_text(json.dumps(out, indent=2))

    months = np.arange(1, chit.n_members - 1)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(months, 100 * an.annual(ts_before.yield_end[1:-1]), color=BLUE, label="Before 1993 (no binding cap)")
    ax.plot(months, 100 * an.annual(ts_after.yield_end[1:-1]), color=ORANGE, label="After 1993 (30% cap)")
    ax.set_xlabel("Month of the chit (40 members)")
    ax.set_ylabel("Yield to end, % a year")
    ax.set_title("Calibrated model: implied rates before and after the 1993 cap", loc="left")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "calibrated_term_structure.png", dpi=150)
    plt.close(fig)
    print(json.dumps({k: out[k] for k in ("fit", "post_cap_check")}, indent=2))
    print("before:", before)
    print("after:", after)


if __name__ == "__main__":
    main()
