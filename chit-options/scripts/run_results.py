"""Solve the equilibrium in every scenario and save results/results.json + figures.

Run from the repo root:  python scripts/run_results.py
"""

import json
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from chit import analysis as an
from chit.mechanics import ChitParams
from chit.members import MemberParams

OUT = Path("results")
BASE_CHIT = ChitParams(n_members=20, instalment=100, commission=0.05, bid_cap=0.40)
BASE_MEMBERS = MemberParams(r_borrow=0.02, r_save=0.005, p_need=0.10)
# A high-demand setting where early discounts would exceed 30% without a cap.
HOT_MEMBERS = MemberParams(r_borrow=0.04, r_save=0.005, p_need=0.20)

# Chart style: validated categorical slots 1-3, recessive axes and grid.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "text.color": INK, "axes.grid": True, "grid.color": "#e4e3df",
    "grid.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "lines.linewidth": 2, "legend.frameon": False,
})


def pct(x):
    return 100 * np.asarray(x)


def scenario_dict(sc):
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in asdict(sc).items()}


def main():
    OUT.mkdir(exist_ok=True)
    results = {"base": {"chit": asdict(BASE_CHIT), "members": asdict(BASE_MEMBERS)}}

    # 1. Base term structure
    sc, ts, e = an.run(BASE_CHIT, BASE_MEMBERS)
    months = np.arange(2, BASE_CHIT.n_members)          # calendar months of the auctions
    results["base"]["scenario"] = scenario_dict(sc)
    results["base"]["term_structure"] = {
        "month": months.tolist(),
        "discount": ts.discount[1:-1].round(6).tolist(),
        "forward_annual": an.annual(ts.forward[1:]).round(6).tolist(),
        "yield_annual": an.annual(ts.yield_end[1:-1]).round(6).tolist(),
        "needy_share": ts.needy_share[1:-1].round(6).tolist(),
    }

    fig, ax = plt.subplots(figsize=(8, 4.5))
    fwd, yld = pct(an.annual(ts.forward[1:])), pct(an.annual(ts.yield_end[1:-1]))
    ax.plot(months, fwd, color=BLUE, label="Forward rate (t to t+1)")
    ax.plot(months, yld, color=ORANGE, label="Yield to end")
    ax.set_xticks(months[::2])
    ax.set_xlabel("Month of the chit (20 members)")
    ax.set_ylabel("Implied rate, % a year")
    ax.set_title("Equilibrium implied rates by month (base case)", loc="left")
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / "term_structure.png", dpi=150)
    plt.close(fig)

    # 2. Where the hump peaks, as needs become more common
    p_values = [0.02, 0.05, 0.10, 0.20, 0.40]
    sweep = an.sensitivity(BASE_CHIT, BASE_MEMBERS, "p_need", p_values)
    results["p_need_sweep"] = [scenario_dict(s) for s, _, _ in sweep]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhspan(25, 100 / 3, color="#e4e3df", label="Practitioner claim (1/4 to 1/3)")
    ax.plot(pct(p_values), [100 * s.forward_peak for s, _, _ in sweep], "o-",
            color=BLUE, markersize=8, label="Forward-rate peak")
    ax.plot(pct(p_values), [100 * s.yield_peak for s, _, _ in sweep], "o-",
            color=ORANGE, markersize=8, label="Yield-to-end peak")
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_xticks(pct(p_values), [f"{v:g}%" for v in pct(p_values)])
    ax.set_ylim(0, 100)
    ax.set_xlabel("Monthly chance a waiting member develops a need")
    ax.set_ylabel("Peak month, % of the way through")
    ax.set_title("Where the implied-rate hump peaks", loc="left")
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT / "peak_position.png", dpi=150)
    plt.close(fig)

    # 3. Other sensitivities (base case)
    results["sensitivities"] = {
        name: [scenario_dict(s) for s, _, _ in an.sensitivity(BASE_CHIT, BASE_MEMBERS, name, vals)]
        for name, vals in {
            "r_borrow": [0.01, 0.02, 0.03, 0.04],
            "r_save": [0.0, 0.005, 0.01],
            "commission": [0.03, 0.05, 0.07],
        }.items()
    }

    # 4. Greeks: change in seat value (fraction of pot) per unit change in a setting
    results["greeks"] = {
        name: round(an.greek(BASE_CHIT, BASE_MEMBERS, name, step), 6)
        for name, step in {"p_need": 0.01, "r_borrow": 0.002, "r_save": 0.001,
                           "commission": 0.005}.items()
    }

    # 5. Bid cap experiment in the high-demand setting
    caps = [0.40, 0.35, 0.30, 0.25]
    cap_runs = [an.run(replace(BASE_CHIT, bid_cap=c), HOT_MEMBERS, f"cap={c}") for c in caps]
    results["bid_cap"] = {"members": asdict(HOT_MEMBERS),
                          "runs": [scenario_dict(s) for s, _, _ in cap_runs],
                          "p_cap_month1": [round(float(t.p_cap[1]), 4) for _, t, _ in cap_runs]}
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(pct(caps), [100 * s.mean_forward for s, _, _ in cap_runs], "o-",
            color=BLUE, markersize=8, label="Average forward rate")
    ax.plot(pct(caps), [100 * s.mean_yield for s, _, _ in cap_runs], "o-",
            color=ORANGE, markersize=8, label="Average yield to end")
    ax.invert_xaxis()
    ax.set_xlabel("Maximum discount allowed (bid cap), % of pot")
    ax.set_ylabel("Implied rate, % a year")
    ax.set_title("Tighter bid caps lower implied rates (high-demand setting)", loc="left")
    ax.legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(OUT / "bid_cap.png", dpi=150)
    plt.close(fig)

    (OUT / "results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({k: results[k] for k in ("greeks",)}, indent=2))
    print("base:", results["base"]["scenario"])


if __name__ == "__main__":
    main()
