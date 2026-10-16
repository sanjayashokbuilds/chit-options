# chit-options

Valuing a seat in a Tamil chit fund with American-option methods (dynamic programming, Longstaff-Schwartz), and solving for equilibrium bidding.

Work in progress: a 24-hour build. Full write-up to follow.

```bash
pip install -e ".[dev]"
pytest
```

## Modules so far

- `chit/mechanics.py`: one chit's payouts, payments, commission and every member's cash flows.
- `chit/rates.py`: NPV and IRR, finding every root (chit cash flows can have two IRRs or none).
- `chit/implied.py`: the term structure implied by winning bids (forward rates, yields to end, per-winner loan rates).
- `chit/members.py`: why members bid. Outside borrowing/saving rates, random cash needs, and simple bidding strategies.
- `chit/simulate.py`: plays out whole chit groups month by month, with English (open ascending) or sealed auctions.
- `chit/env.py`: the chit as one member sees it when all rivals bid myopically; the exact small state (month, own need, needy rivals).
- `chit/dp.py`: backward-induction dynamic programme: the seat's value and the optimal bid / pass map (exercise boundary).
- `chit/lsm.py`: Longstaff-Schwartz least-squares Monte Carlo for the same problem, valued out of sample.

## Validation of the numerical methods

- **DP vs brute force:** in a 4-member chit, the DP's value equals the best of all 1,024 possible policies.
- **DP vs simulator:** playing the DP's policy in the independent month-by-month simulator reproduces the DP's value within Monte Carlo error.
- **LSM vs DP:** with an indicator basis (one regression column per state), LSM's out-of-sample value matches the DP within Monte Carlo error across seeds (mean z-score about 0 over 8 seeds, N = 20).
- **Basis choice matters:** a smooth cubic basis, the textbook LSM choice, loses value (e.g. about 0.5% of the pot at N = 20). The optimal rule has a step between "no needy rival" and "one needy rival", which a cubic can't represent.

## Rules and conventions used

| Setting | Default | Source / status |
|---|---|---|
| Foreman's commission | 5% of pot per auction | Legal cap raised from 5% to 7% by the Chit Funds (Amendment) Act 2019 ([PRS India](https://prsindia.org/billtrack/the-chit-funds-amendment-bill-2019)). Klonner & Rai report 5-6% in practice. |
| Maximum discount | 40% of pot | 30% cap enforced from 1993, relaxed to 40% in 2002, per [Klonner & Rai](https://web.williams.edu/Economics/rai/adverse-08-9-1.pdf). Current statutory text still to confirm. |
| Foreman's month | Foreman takes month 0's pot at zero discount, no commission | Matches the company data in Klonner & Rai. |
| Dividend | (discount - commission) split equally among all N members | Modelling choice. |
| Minimum bid | equal to the commission | Keeps dividends non-negative. Modelling choice. |
| Cash needs | Each month a waiting member gets a need with probability `p_need`; it lasts until they win | Modelling choice. |
| Outside rates | Borrow at 2%/month, save at 0.5%/month | Placeholder values, to calibrate. |
| Auction format | English (winner pays second-highest willingness); sealed also available | Which format real chits use is still to verify. |
| Ties | Broken by lottery (e.g. several members at the cap) | Believed to match practice; to verify. |
| Information (DP/LSM) | The valued member knows how many rivals are in need | Full-information benchmark: an upper bound on the seat's value. |
| Actions (DP/LSM) | Bid up to the cap, or sit the month out (never win by lottery when passing; no bidding just to raise others' price) | Modelling choice. |
| Discounting (DP/LSM) | Next month's money is worth 1/(1+r), with r = borrowing rate while in need, saving rate otherwise | Modelling choice. |
