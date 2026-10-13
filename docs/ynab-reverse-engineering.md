# Reverse engineering YNAB's budget engine

`adi/budget/` is a clean-room reimplementation of the budgeting model in
YNAB ("You Need A Budget"), used to run American Dream Index households
through a zero-based monthly budget (`python -m adi budget`). This document
records how the model was recovered, what each rule rests on, and what is
inferred rather than observed.

**Clean room.** No YNAB code is copied or translated. The budget engine is
only served to signed-in users. We did not sign in or try to reach
authenticated resources. Every rule comes from public material: YNAB's
published API contract, its open-source (Apache-2.0) JavaScript SDK, and its
public support documentation. The implementation is original Python written
from those behavioural descriptions.

## Tooling and artifacts

The analysis used [REA](https://github.com/morluto/rea) 6.4.0
(`rea-agents`), built from source.

| Artifact | How it was obtained | Identity |
| --- | --- | --- |
| `app.ynab.com` sign-in shell, 13 webpack packs + `assets/packs/manifest.json` | Public static assets (no login) | manifest lists 220 entries |
| YNAB API OpenAPI spec v1.87.0 | `https://api.ynab.com/papi/open_api_spec.yaml` | sha256 `69411d59…ebf26f` |
| `ynab` SDK 4.5.0 | `npm pack ynab` | tarball sha256 `f3c86671…122093` |
| Support articles | `support.ynab.com` (`.md` pages indexed by `/llms.txt`) | URLs below |

**REA findings**

* `rea analyze-javascript-application` on the SDK package (evidence
  `ev_e6b6ad2b…74e`, root digest `205a4990…e7a`):
  * 605 JavaScript files parsed with no parse failures; 139 modules and
    5,899 findings.
  * The recovered route endpoints were `/plans` and `/user`.
  * The money helper `convertMilliUnitsToCurrencyAmount` sits in
    `dist/utils.js` (asset sha256 `b8abe3bb…5be`). It rounds to the
    currency's precision with `Math.round`, and `adi/budget/money.py`
    reproduces that.
  * REA's stated limitations apply: the analysis is static only, and no
    bundle code was executed.
* Static inspection of the web manifest showed the public packs are the
  Rails shell:
  * They cover authentication, admin, marketing and analytics.
  * Two event names in pack 953 (`Budget_Overbudgeted`,
    `Budget_FixedOverbudgeting`) show that over-assigning is a state the
    product tracks.
  * The budget engine bundle is not among them. It loads only after sign-in,
    so the engine itself was reconstructed from its documented behaviour and
    the API's field semantics.

## Recovered rules

Tags: **[S]** stated by YNAB (API spec or support docs). **[O]** observed in
shipped code via REA. **[I]** inferred. Each [I] rule is the simplest model
consistent with the stated behaviour, and the tests pin it down.

### Money
* [S] Amounts are int64 milliunits, where 1000 = one currency unit
  ([API formats](https://api.ynab.com/#formats)).
* [O] Conversion to currency rounds at the currency's decimal digits, with
  halves rounded toward +∞ (SDK `utils.js`).
* [I] Targets spread over several months round the monthly amount up to the
  next milliunit.

### Ready to Assign (`month.to_be_budgeted`)
* [S] Ready to Assign builds month to month as follows
  ([plan header](https://support.ynab.com/en_us/the-plan-header-BkmiuJ_C9)):
  * start from last month's leftover;
  * add this month's Inflow: Ready to Assign transactions and starting
    balances;
  * subtract last month's cash overspending;
  * subtract what is assigned this month and in future months.
* [S] Money assigned in a future month is no longer available now.
  Over-assigning a future month makes that month negative while the current
  month can still show 0
  ([month ahead](https://support.ynab.com/en_us/getting-a-month-ahead-HJidy13C5),
  [negative RTA](https://support.ynab.com/en_us/when-ready-to-assign-is-negative-an-overview-HylZA0zCc)).
* [I] Displayed RTA(M) is the running balance R(M) when R(M) < 0. Otherwise
  it is max(0, min over m ≥ M of R(m)). See `Plan.compute`.
* [S] Income only counts once it is received. There is no "income for next
  month" in the current product.

### Category rollover and overspending
* [S] Positive Available carries forward. Negative Available is reset to 0.
  Assigned resets each month
  ([month rollover](https://support.ynab.com/en_us/when-the-month-rolls-over-a-guide-rkyyd6qC9)).
* [I] Available = carry + assigned + activity.
* [S] Cash overspending is subtracted from next month's Ready to Assign.
  Credit overspending is not: it becomes card debt
  ([overspending](https://support.ynab.com/en_us/overspending-in-ynab-a-guide-ryWoxEyi)).
* [S] When a category is overspent with both cash and credit, the cash
  portion is taken first.

### Credit cards
* [S] Funded card spending moves the funded amount from the category to the
  card's payment category. For example, a $150 purchase against $100
  Available moves $100, and the other $50 is credit overspending
  ([card overspending](https://support.ynab.com/en_us/credit-card-overspending-an-overview-HkMGpSbJs)).
* [S] Payments from cash accounts reduce the payment category. Overpaying it
  is cash overspending.
* [S] Refunds move money back out of the payment category
  ([refunds](https://support.ynab.com/en_us/credit-card-refunds-and-returns-H1J7qDWkj)).
* [S] Starting balances and interest move nothing.
* [S] A card transaction cannot be categorised to a payment category (API
  spec).

### Transfers and tracking accounts
* [S] Transfers between two budget accounts, or between two tracking
  accounts, take no category. A transfer that crosses the budget boundary
  needs one
  ([transfers](https://support.ynab.com/en_us/transfer-transactions-a-guide-HJOsZz4Jj)).

### Age of Money
* [S] Age of Money averages the last ten cash outflows, including card
  payments.
  * It needs ten outflows before it shows a value.
  * Transfers and starting balances are not counted.
  * Card purchases count only once the card is paid
    ([Age of Money](https://support.ynab.com/en_us/age-of-money-H1ZS84W1s)).
* [I] Inflows are matched to outflows first in, first out. Each outflow's
  age is the dollar-weighted wait of the dollars it consumed, and the result
  is a simple mean over the last ten outflows.

### Targets (`goal_type`, `goal_under_funded`, …)
* [S] The target types and their fields come from the API spec: `TB`,
  `TBD`, `MF`, `NEED`, `DEBT` and `goal_needs_whole_amount`.
* [S] Set aside asks for the full amount every period. Refill asks only to
  top up to the target. Yearly and custom targets are spread evenly over the
  months to the due date
  ([targets](https://support.ynab.com/en_us/getting-started-with-targets-ryAEP08xC)).
* [I] Underfunded formulas, where `start` is the Available carried in:
  * MF/DEBT: `target − assigned`
  * TB: `target − (start + assigned)`
  * TBD: `ceil((target − start) / months_left) − assigned`
  * NEED refill: `ceil((target − start) / months_left) − assigned`
  * NEED set aside: `ceil((target − funded_this_period) / months_left) − assigned`
* [S] Underfunded auto-assign skips undated balance targets and stops when
  Ready to Assign reaches 0
  ([underfunded](https://support.ynab.com/en_us/underfunded-a-guide-BJwPhQO09)).
  * Our version funds in category order. YNAB first orders by overspending
    and due date.

### Not modelled
* Weekly targets.
* Snoozing.
* Card payoff-by-date targets.
* Loan amortisation (`DEBT` is treated as a fixed monthly payment).
* Cards carrying a positive balance (YNAB treats these like cash).
* Split transactions.
* Scheduled transactions.
* Reconciliation.

## Applying it to the American Dream Index

`adi/budget/household.py` turns an index year and scenario into a 12-month
plan.

**Categories and targets.** Each index line item becomes one category, with
a target that fits how the bill behaves:
* monthly bills: NEED refill;
* annual and semi-annual bills (property tax, insurance, registration):
  NEED set aside with a due date;
* irregular expenses: evenly timed sinking funds;
* savings: MF.

**Income.** Biweekly take-home pay is the gross income minus tax
interpolated from the index's TAXSIM grid.

**Spending.**
* Everyday spending goes on a card that is paid in full each month.
* Retirement saving goes to an off-budget 401(k).

**Assigning.**
* Each month, income is assigned in priority order: bills, then necessities,
  then discretionary spending, then saving.
* Bills are always paid.
* Flexible spending and saving are cut back to what is funded.

**Warm-up year.** A warm-up year runs first, so sinking funds and Age of
Money are in a steady state when the reported year starts.

**Check.** At the gross income the index says the lifestyle needs, the plan
funds 100% of it with no overspending (`tests/test_budget.py`).

**Results for 2025** at the median married-couple income ($132,100 gross):

| | Two earners + childcare (A) | One earner (B) |
| --- | --- | --- |
| Take-home pay | $111,285 | $109,881 |
| Lifestyle funded | 66% | 77% |
| Bills, childcare, healthcare, technology | 100% | 100% |
| Housing (incl. down-payment saving, maintenance) | 78% | 86% |
| Transportation (incl. saving for the next car) | 57% | 74% |
| Vacations | 17% | 79% |
| Retirement saving | 4% | 17% |
| Age of Money, December | 47 days | 64 days |

The budget pays every bill, but what goes without is the forward-looking
part of the dream: retirement, the next car, the next house, and vacations.
That gap is what the index's "share of income" figures measure. It shows up
here as targets that never get funded, rather than as debt.

Reproduce with `python -m adi budget --scenario A` (or `B`, `--year`,
`--gross`). Outputs are written to
`data/processed/budget_<year>_<scenario>_{categories,months}.csv`.
