# American Dream Index: methodology

The index answers one question for each year from 1980 to 2025:

> How much **pre-tax** income would a family of four need to buy, run and
> keep a comfortable middle-class lifestyle in that year, including saving to
> retire at 55–60, and how does that compare with what families earned?

The cost is a flow: what it takes *each year* to sustain the lifestyle
(mortgage payments, replacement reserves for cars and appliances, saving for
the down payment and for retirement, taxes), not the sum of purchase prices.

Every assumption below is a key in [`config/assumptions.toml`](../config/assumptions.toml).
Results are in `data/processed/`. Numbers quoted here are from the default
configuration.

## 1. Households and benchmarks

| | Scenario A | Scenario B |
|---|---|---|
| Earners | Two (55% / 45% wage split) | One |
| Children (ages 2 and 4) | Full-time paid centre care | Cared for at home |
| Social Security | Two worker benefits | Worker + spousal benefit |
| Pension expectation | Two workers × DB coverage share | One worker |

Scenario B prices the 1980-style single-earner arrangement without treating
the at-home parent's care as free: its cost to the family is the second
income it gives up, which shows up as the gap between the A and B lines and
the income benchmarks.

**Income benchmarks** (all current dollars):

* Median household income: Census CPS ASEC Historical Income Table H-5, all races.
* Median married-couple family income: Census Table F-7.
* Median full-time earnings: BLS median usual weekly earnings of full-time
  wage and salary workers (FRED `LEU0252881500A`) × 52. The index divides the
  pre-tax cost by this to give **the number of full-time median paychecks
  needed**.

Census lists 2013 and 2017 twice (questionnaire redesign, processing update);
the model uses the first row, the one consistent with later years.

## 2. Components

Two pricing methods are used.

1. **Own historical series** where a good one exists.
2. **Anchor and index**: a national-average dollar figure for the anchor year
   (2024) carried to other years on the price index for that item. A
   CPI item index that starts late is extended with the growth of a broader
   index (each splice is listed in `adi/data.py`).

### Why some items follow actual spending instead of a price index

CPI indexes are quality-adjusted: they measure the price of an *unchanged*
item. Over 45 years that breaks down for goods that changed beyond
recognition. The CPI television index fell about 99% between 1980 and 2024,
so a 2024-quality 60" TV priced on that index would have cost about $53,000 in
1980. Phones (landline → smartphone) and clothing (cheap imports) have the
same problem in milder form. For these categories the index follows what
married couples with children **actually spent** on the category each year
(BLS Consumer Expenditure Survey, 1988 on, 3-year centered average; CPI-U
before 1988). That prices an *era-typical* version of the item rather than
today's version at yesterday's prices. Config keys let you switch any of
these back to the item CPI.

### Housing

* **Home price**: 2024 national median existing-home price (NAR, $407,500;
  the median existing home is roughly 3 bedrooms / 2 baths), moved with the
  FHFA all-transactions house price index (`USSTHPI`), a repeat-sales index
  that holds quality roughly constant. The 1980 result ($62,100) matches
  NAR's 1980 median existing-home price.
* **Mortgage**: 20% down, 30-year fixed at the Freddie Mac PMMS annual
  average rate (`MORTGAGE30US`). Payment is principal and interest.
* **Down payment**: saved over the 10 years before buying (20% of the price ÷ 10
  per year).
* **Property tax** 1.0% and **maintenance** 1.0% of value per year.
* **Homeowners insurance**: 2024 average premium, carried on the CPI for
  tenants' and household insurance (1998+), core CPI before.
* **Utilities**: CE married couples with children, "utilities, fuels and
  public services" less telephone, carried on the CPI for fuels and utilities.

### Transportation (two cars, 15,000 miles each)

AAA *Your Driving Costs* 2024, per new vehicle: depreciation, finance,
fuel, insurance, maintenance/repair/tires, and license/registration/taxes.
Fuel, insurance, maintenance and fees follow their CPI components.
Finance cost also moves with the Fed's 48-month new-car loan rate
(`TERMCBAUTO48NS`).

### Childcare

Child Care Aware of America 2024 national average price of centre care for
an infant and a preschooler, carried on the CPI for day care and preschool
(1991+). Before 1991 the only CPI that includes childcare is dominated by
college tuition (it rose 2.7× in 1980–91 while wages rose 1.5×), so childcare
is carried back on average hourly earnings of production and nonsupervisory
workers (`AHETPI`): childcare prices are mostly wages.

### Food

CE married couples with children, food at home and food away from home, on
the CPI for each.

### Household goods

A replacement reserve (price ÷ expected life) for a 60" TV, refrigerator,
freezer, washer, dryer, microwave and range, plus furniture. Era-typical
spending method (see above).

### Technology

Two smartphones (device every three years plus a plan each), home internet
and a cable package. Phone and internet follow CE telephone spending of
married couples with children (era-typical: landline + long distance in the
1980s); cable follows the CPI for cable, satellite and streaming TV.

### Healthcare

The worker's share of an employer family plan premium from the KFF Employer
Health Benefits Survey (1999 on). Before 1999, what CE married couples with
children paid for health insurance (1988–98), then the CPI for medical care
services. Out-of-pocket spending (CE healthcare less insurance) follows the
medical care CPI.

### Vacations

A family of four: one domestic trip a year (airfare, 6 hotel nights, meals and
activities) and one international trip every five years (8 nights), on the
CPI for airline fares, hotels and food away from home.

### Other necessities

Clothing, personal care, housekeeping supplies, entertainment and
miscellaneous spending of CE married couples with children, era-typical
method.

## 3. Retirement (retire at 57.5)

For parents aged 35 in year *t*, in year-*t* dollars and real returns:

1. **Retired spending**: the working family's costs, without the mortgage
   (paid off), childcare or car loans, with food, goods and travel scaled for
   a couple (55%–75%). Before Medicare (age 65), the couple buys health
   insurance on the individual market at 85% of the total employer family
   premium. From 65, Medicare Part B, Medigap and Part D.
2. **Social Security**, claimed at 62: the medium-earner benefit is 41% of
   career-average wage-indexed earnings at full retirement age (SSA Trustees
   Report Table V.C7 has held it at 41–43% for workers retiring since 2005),
   applied to median full-time earnings. The early-claiming cut follows the
   parents' birth cohort: 80% of the full benefit at 62 for those born in
   1937 or earlier, 70% for those born in 1960 or later. Scenario B adds a
   spousal benefit (32.5%–37.5% of the worker's benefit at 62).
3. **Pensions**: the share of private-sector workers in a defined-benefit
   plan that year (DOL Form 5500 bulletins to 1998, BLS National Compensation
   Survey since; 38% in 1980, 9% in 2025) × a pension worth 25% of earnings.
4. **Horizon**: the longer-lived spouse's period life expectancy at 65 (SSA
   Trustees Report Table V.A4) plus 3 years.
5. **Nest egg**: present value at 57.5 of spending minus income through the
   horizon, at a 3.0% real return.
6. **Annual saving**: level contributions from age 30 to 57.5 at a 4.5% real
   return that reach the nest egg.

Savings are treated as after-tax (Roth-style), so retirement withdrawals are
untaxed and contributions don't reduce taxable income.

## 4. Taxes

The index is the **gross** income at which wages minus federal income tax,
state income tax and the employee share of FICA equal the lifestyle's
after-tax cost (all of the above).

* NBER **TAXSIM 35** computes taxes for a married couple filing jointly with
  two children (ages 2 and 4). Inputs: wages (split 55/45 in scenario A),
  mortgage interest (average over the loan's first 10 years), property tax
  and childcare spending. TAXSIM itemizes when that beats the standard
  deduction and applies the child tax credit, the child and dependent care
  credit and every other provision of each year's law.
* **State tax**: run for all 50 states and DC and averaged with each year's
  state population as weights (Census estimates via FRED).
* Each year is run at 16 incomes from 0.5× to 3.5× median married-couple
  income, and the required income is found by interpolation. Results are
  cached in `data/raw/taxsim/`.
* TAXSIM 35 covers tax law through 2023. For 2024–2025 the model applies
  2023 law to CPI-deflated amounts and re-inflates the tax. Brackets,
  deductions and the FICA wage base are inflation indexed, so this is close;
  it misses the 2025 law's larger standard deduction and child credit.

## 5. Caveats

* **Quality and substitution**: no fixed basket is right for 45 years. The
  model mixes constant-quality prices (housing, food, services) with
  era-typical spending (electronics, clothing). Constant-quality prices for
  cars (CPI new vehicles) make past cars look relatively expensive.
* **One national household.** Housing, childcare and taxes vary enormously
  by place; the interactive page's home-price slider gives a rough local
  adjustment. County-level data is a natural next step (FHFA county HPI,
  BEA county income, the DOL National Database of Childcare Prices from 2008).
* **Social Security is scheduled, not payable.** The Trustees project the
  retirement trust fund to be depleted in the 2030s, after which benefits
  would be cut by about a fifth without legislation. Planning on payable
  benefits raises recent years' retirement saving.
* **Retirement return assumptions** are fixed (4.5% / 3.0% real). Real
  interest rates were far higher in the 1980s, which made saving cheaper
  then; holding returns fixed isolates the price of the lifestyle.
* **CE spending is for the average married couple with children**, whose
  income is above the median. The levels set the 2024 anchors; only the
  year-to-year changes carry the history.
* **Taxes are endogenous.** Because the required income is far above the
  median, the household pays above-median tax rates. That is part of the
  real cost of the lifestyle, and in 1980, with high, unindexed brackets, it
  was a large part.

## 6. Sources

| Data | Source | Series / table |
|---|---|---|
| House prices | FHFA via FRED | `USSTHPI` |
| Mortgage rates | Freddie Mac PMMS via FRED | `MORTGAGE30US` |
| Auto loan rates | Federal Reserve G.19 via FRED | `TERMCBAUTO48NS` |
| Consumer prices | BLS CPI-U, U.S. city average, NSA | `CUUR0000*` (see `adi/data.py`) |
| PCE prices (pre-1998 splices) | BEA via FRED | `DHAPRG3A086NBEA`, `DTCSRG3A086NBEA`, `DTCERG3A086NBEA`, `DINTRG3A086NBEA` |
| Wages (childcare splice) | BLS CES via FRED | `AHETPI` |
| Family spending | BLS Consumer Expenditure Survey | composition of consumer unit: married couple with children |
| Household & family income | Census CPS ASEC | Tables H-5, F-7 |
| Full-time earnings | BLS CPS via FRED | `LEU0252881500A` |
| State population | Census via FRED | `{ST}POP` |
| Taxes | NBER TAXSIM 35 | taxsim.nber.org |
| Health premiums | KFF Employer Health Benefits Survey | worker contribution, family coverage |
| Life expectancy | SSA 2026 Trustees Report | Table V.A4 |
| Pension coverage | DOL Private Pension Plan Bulletin; BLS NCS | Table E4; `NBU29000000000000026291` |
| Social Security | SSA | Trustees Report Table V.C7; early-retirement reduction schedule |
| 2024 anchors | AAA, Child Care Aware of America, NAR, KFF, BLS CE | see `config/assumptions.toml` |
