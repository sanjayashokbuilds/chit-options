# chit-options

Valuing a seat in a Tamil chit fund with American-option methods (dynamic programming, Longstaff-Schwartz), and solving for equilibrium bidding.

Work in progress: a 24-hour build. Full write-up to follow.

```bash
pip install -e ".[dev,results]"
pytest                          # 37 tests
python scripts/run_results.py   # solves every scenario, writes results/ (about 20 s)
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
- `chit/equilibrium.py`: symmetric equilibrium. Everyone bids up to their indifference price; best responses are iterated (with damping) until the willingness table stops changing.
- `chit/analysis.py`: the exact equilibrium term structure (the number of needy members is a Markov chain, so its distribution is pushed forward month by month), sensitivities and finite-difference "Greeks".
- `scripts/run_results.py`: every scenario, `results/results.json` and the figures.

## Validation of the numerical methods

- **DP vs brute force:** in a 4-member chit, the DP's value equals the best of all 1,024 possible policies.
- **DP vs simulator:** playing the DP's policy in the independent month-by-month simulator reproduces the DP's value within Monte Carlo error.
- **LSM vs DP:** with an indicator basis (one regression column per state), LSM's out-of-sample value matches the DP within Monte Carlo error across seeds (mean z-score about 0 over 8 seeds, N = 20).
- **Equilibrium:** converges to the same table (to 1e-10) from three different starting points (myopic, everyone at the minimum, everyone at the cap). A member's gain from deviating is zero to machine precision. Its value matches the simulator.
- **Exact term structure vs simulation:** month-by-month average discounts and forward rates agree within Monte Carlo error.
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

## Results so far (model output, not yet compared with data)

Base case: 20 members, 2%/month borrowing, 0.5%/month saving, 10% monthly chance of a need, 5% commission, 40% cap.

![Equilibrium implied rates](results/term_structure.png)

- **Implied rates are hump-shaped.** The yield to end peaks around month 9 (45% of the way through) and the forward rate around month 13 (65%). The average is about 12% a year.
- **The peak's position depends on how common needs are, not on the borrowing rate.** The borrowing rate moves the whole curve up or down (average yield 8% a year at 1%/month borrowing, 20% at 4%) but leaves the peak where it is. Rare needs (2-5% a month) put the yield peak at 20-25% of the tenure, close to the practitioner claim of 1/4 to 1/3. Common needs push it late. The forward-rate peak is never earlier than 40% in the range tested.

![Peak position](results/peak_position.png)

- **So the model can produce an early-to-mid peak, but only under some settings and for one rate measure.** That is a conditional result, not a confirmation. Calibrating the need probability to real data is the next step.
- **Proposed explanation (to be decomposed formally):** two forces pull against each other. Unmet needs pile up among members still waiting (the needy share rises from 19% in month 1 to about 41% by month 10 in the base case), which keeps discounts high. Meanwhile the shrinking time left makes an early pot worth less, which pulls discounts down. The yield is the discount spread over the months left, so it rises while discounts fall slowly and falls once they collapse.
- **Bid caps:** in the base case the cap never binds. In a high-demand setting (20% need chance, 4%/month borrowing), where early discounts reach about 33%, tightening the cap lowers average implied rates: forward rate 27.5% a year (cap 40%), 24.1% (cap 30%), 18.9% (cap 25%). That matches the direction of the fall in rates after the 1993 cap reported by Eeckhout & Munshi, as cited by Klonner & Rai.

![Bid cap](results/bid_cap.png)

- **"Greeks" (change in equilibrium seat value, as a fraction of the pot, per unit change in a setting):** commission -0.91, borrowing rate -0.70, saving rate +0.58, need probability -0.25. For example, a 1 percentage point higher commission costs a seat about 0.9% of the pot.

## Limitations so far

- Members are identical and know how many others are in need (full information). Klonner's work stresses private information, which we don't model yet.
- No default risk; the foreman bears it in practice and it affects bids (Klonner & Rai).
- Outside rates and the need probability are placeholders, not calibrated.
- Members drop out at their indifference price; nobody bids just to push up the price others pay.
