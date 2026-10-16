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
