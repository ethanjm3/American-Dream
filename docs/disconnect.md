# Why the index says "cheaper" when it feels more expensive

The headline result is that the American Dream lifestyle cost 2.2× the
median married couple's income in 1980 and 1.65× in 2025, so it looks
cheaper today. That runs against most people's experience. This note
measures where the gap between the index and that experience comes from.
Everything here is reproducible with `python -m adi disconnect`, which
writes `data/processed/disconnect_*.csv` and charts 05–06.

**Short answer: the lifestyle did not get cheaper per worker.** It took 3.7
median full-time paychecks in 1980, 3.4 in 1985 and 3.5 in 2025. Married
couples can cover more of it because they now bring home 2.1 paychecks
instead of 1.7, and because the families who are still married with children
are a smaller, richer group. The pieces that define the Dream (childcare,
health insurance, retirement, and since 2019 the house) take more paychecks;
the pieces that got cheaper are cars, clothes, food and taxes. Since 2019 it
has gotten clearly worse.

## 1. The yardstick decides the answer

Pre-tax cost of the two-earner lifestyle as a multiple of each income:

| Measured against | 1980 | 1990 | 2019 | 2021 | 2025 | Change since 1980 | since 1990 | since 2019 |
|---|---|---|---|---|---|---|---|---|
| One full-time paycheck (BLS median) | 3.73 | 3.55 | 3.27 | 2.92 | 3.48 | −7% | −2% | **+6%** |
| Median household (Census H-5) | 2.87 | 2.54 | 2.27 | 2.14 | 2.49 | −13% | −2% | **+10%** |
| Family, householder 25–34 (F-11) | 2.49 | 2.42 | 2.20 | 1.99 | 2.19 | −12% | −9% | 0% |
| Median married couple (F-7) | 2.20 | 1.91 | 1.53 | 1.42 | 1.65 | −25% | −14% | **+8%** |
| Married couple with children (F-10) | 2.09 | 1.85 | 1.40 | 1.28 | 1.46 | −30% | −21% | +4% |

From 1980 to 2025 the lifestyle's cost rose 4.3×. A median full-time paycheck
rose 4.6× and median household income 4.9×, so against those the change is
small. Married couples' income rose 5.7× and married parents' 6.2×, so against
those it looks like a big improvement. (Consumer prices rose 3.9×.)

![Yardsticks](../charts/05_yardsticks.png)

## 2. Couples got there by working more, not by the Dream getting cheaper

Split the change in "cost ÷ married-couple income" into "cost ÷ one
paycheck" times "paychecks per couple":

| Period | Cost ÷ couple's income | from cost per paycheck | from more paychecks per couple | Share from more paychecks |
|---|---|---|---|---|
| 1980 → 2025 | 2.20 → 1.65 | −7% | −20% | **76%** |
| 1985 → 2025 | 1.93 → 1.65 | **+4%** | −18% | **all of it** |
| 1990 → 2025 | 1.91 → 1.65 | −2% | −12% | 86% |
| 2019 → 2025 | 1.53 → 1.65 | **+6%** | +1% | — |

(Each factor's percent change; the share column splits the total in log terms.)

The median married couple earned 1.70 full-time paychecks in 1980 and 2.11
in 2025. Married parents went from 1.78 to 2.39. That is mostly the second
earner: wives' work and pay. It isn't free. The second job is what creates
the childcare bill, and in 2025 the two-earner version of the lifestyle needs
0.6 more paychecks than the one-earner version (3.48 vs 2.86): 0.47 for
childcare and 0.20 for the extra tax on the income needed to pay for it.

**Selection compounds it.** Married couples with children were 31% of
households in 1980 and are 17% in 2025 (Census HH-1, FM-1); married couples
fell from 61% to 47%. The families who still fit the picture are,
increasingly, the ones who can afford it. Their median income is not "most
Americans'" income.

## 3. What got dearer and what got cheaper, in paychecks

| Category | 1980 | 2019 | 2025 | Change since 1980 | since 2019 |
|---|---|---|---|---|---|
| Housing | 0.80 | 0.57 | 0.78 | −0.02 | **+0.21** |
| Childcare | 0.37 | 0.48 | 0.47 | **+0.09** | −0.01 |
| Healthcare | 0.06 | 0.18 | 0.16 | **+0.10** | −0.02 |
| Retirement saving | 0.21 | 0.31 | 0.30 | **+0.09** | −0.01 |
| Technology | 0.06 | 0.09 | 0.07 | +0.01 | −0.02 |
| Transportation | 0.47 | 0.39 | 0.37 | −0.10 | −0.02 |
| Food | 0.29 | 0.25 | 0.25 | −0.04 | 0.00 |
| Other necessities | 0.29 | 0.20 | 0.19 | −0.10 | −0.01 |
| Household goods + vacations | 0.13 | 0.13 | 0.11 | −0.02 | −0.02 |
| Taxes | 1.05 | 0.68 | 0.79 | **−0.25** | +0.11 |
| **Total** | **3.73** | **3.27** | **3.48** | **−0.25** | **+0.21** |

![Paycheck changes](../charts/06_paycheck_changes.png)

* **Taxes explain all of the per-paycheck improvement since 1980.** Excluding
  taxes, the lifestyle cost 2.69 paychecks in 1980 and 2.69 in 2025. In 1980,
  the high income the lifestyle required ran into high, unindexed brackets;
  the 1981 and 1986 tax laws, inflation indexing and the child tax credit
  lowered that. Few people think of taxes as part of the price of a home and
  kids, so this improvement goes unnoticed.
* **The Dream's defining pieces got dearer.** Childcare, health insurance and
  retirement each take about 0.1 more paychecks. Retirement costs more because
  people live longer (the longer-lived spouse's life expectancy at 65 rose from
  18.4 to 20.7 years), traditional pensions shrank from 38% of private workers
  to 9%, and claiming Social Security at 62 now pays 70% of the full benefit
  instead of 75–80%.
* **What got cheaper is stuff.** Cars (−0.10), clothing, furnishings and
  entertainment (−0.10) and food (−0.04) are cheaper relative to pay. These
  are real gains, but they aren't what people mean by the Dream, and cheaper
  TVs don't offset a daycare bill.

## 4. The reference point: 1980 was the worst year, and 2019–25 got worse

1980–81 is the least affordable point in the series: 30-year mortgages at
13.7% (16.6% in 1981) and bracket creep. Measured from 1985 instead, the cost
per paycheck is **up** 4%. Most people's reference point is not 1980 but the
last 5–10 years, and since 2019:

* cost per paycheck is up 6% (+19% since 2021),
* cost against the median household's income is up 10%,
* and all of it is housing: +0.21 paychecks from higher prices and rates.

## 5. Sticker prices vs. payments

| | 1980 | 1990 | 2000 | 2006 | 2012 | 2021 | 2025 |
|---|---|---|---|---|---|---|---|
| Typical home price ÷ median household income | 3.5 | 3.4 | 3.4 | 4.7 | 3.7 | 4.5 | **4.8** |
| Mortgage rate | 13.7% | 10.1% | 8.1% | 6.4% | 3.7% | 3.0% | 6.6% |
| Payment (P&I, 20% down) ÷ household income | **39%** | 29% | 24% | 28% | 16% | 18% | 30% |

Home prices relative to income are at a record, 38% above 1980. The monthly
payment is lower than 1980's only because 1980's mortgage rates were twice
today's. People compare prices ("my parents paid $60,000"), and recent buyers
compare payments with 2012–2021, when they were half of today's.

## 6. Do the model's assumptions flatter today?

The 1980→2025 change under alternative assumptions (two-earner lifestyle):

| Variant | Paychecks 1980 → 2019 → 2025 | Change since 1980, paychecks | vs. married couples |
|---|---|---|---|
| Baseline | 3.73 → 3.27 → 3.48 | −7% | −25% |
| Market interest rates for retirement returns | 3.49 → 3.50 → 3.48 | **0%** | −20% |
| Social Security cut to 77% after 2033 | 3.73 → 3.33 → 3.54 | −5% | −24% |
| Actual median new-home prices | 3.75 → 3.41 → 3.43 | −8% | −26% |
| Out-of-pocket health at Milliman's level | 3.78 → 3.34 → 3.54 | −6% | −24% |
| **All four together** | 3.55 → **3.83** → 3.56 | **0%** | −19% |
| Constant-quality basket (item CPIs) | 6.70 → 3.30 → 3.52 | −48% | −58% |

* **Interest rates matter most.** Bond yields in the 1980s implied expected
  real returns of 6–9% for a balanced portfolio; since 2010, 2–4%. Pricing retirement at each
  era's market rates erases the per-paycheck improvement. With all four
  cautious choices the lifestyle costs the same 3.5–3.6 paychecks in 1980 and
  2025, and 2019 becomes the most expensive year.
* **The other direction is much bigger, and wrong.** Pricing today's basket
  with quality-adjusted CPIs makes 1980 look absurdly expensive (6.7
  paychecks), which is why the index uses what families actually spent on
  electronics, clothing and cars. That choice is conservative, not flattering.
* Every variant still shows a large improvement against married couples'
  income, because that comes from the denominator (sections 2–3), not from
  the cost.

## What the index doesn't price

The lifestyle you defined doesn't include college, which is the single
fastest-rising family cost (the CPI for college tuition and fees rose 13.5×
from 1980 to 2025, versus 3.9× for all prices), or the larger down
payment a buyer needs to save while home prices outrun incomes. It also
measures a national median family; in high-cost places housing and
childcare run far higher (infant centre care averaged $26,343 a year in
Massachusetts in 2024, against about $15,600 nationally). All three would push the index toward the
popular perception.

## Bottom line

| Claim | Holds? |
|---|---|
| "The Dream costs less of a married couple's income than in 1980" | Yes, −25%, but three-quarters of that is couples working more |
| "The Dream costs fewer paychecks than in 1980" | Barely (−7%), and only because of lower taxes; flat with market interest rates |
| "The Dream costs fewer paychecks than in the mid-1980s" | No, +4% since 1985 |
| "The Dream got more expensive recently" | Yes, +6% per paycheck since 2019, +19% since 2021, all housing |
| "Houses are less affordable than ever" | By price, yes (4.8× household income, a record); by payment, no (30% vs 39% in 1980) |
