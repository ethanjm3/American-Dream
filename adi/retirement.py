"""Annual savings needed to retire at 55-60 and keep the lifestyle.

For a family whose parents are ``household.parent_age`` in year *t*:

1. **Retired spending** -- the working family's costs, minus the mortgage,
   childcare and the children's share of food and goods, plus health
   insurance bought on the individual market until Medicare at 65, then
   Medicare premiums and Medigap/Part D.
2. **Retirement income** -- Social Security claimed at ``ss_claim_age``
   (benefits for the parents' birth cohort, so the rising full retirement
   age shrinks early-claiming benefits), plus a defined-benefit pension
   weighted by the share of private workers who had one in year *t*.
3. **Nest egg** -- present value at the retirement age of spending minus
   income, through the longer-lived spouse's life expectancy plus a buffer.
4. **Annual saving** -- level contributions from ``start_saving_age`` to the
   retirement age that grow to the nest egg.

Everything is in year-*t* dollars with real (after-inflation) returns, so
year-*t* prices, earnings, and life expectancy define year *t*'s requirement.
Savings are treated as after-tax (Roth-style), so retirement withdrawals are
untaxed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data


def full_retirement_age(birth_year: float) -> float:
    """Social Security full retirement age by birth year (1983 amendments)."""
    if birth_year <= 1937:
        return 65.0
    if birth_year <= 1942:
        return 65 + (birth_year - 1937) * 2 / 12
    if birth_year <= 1954:
        return 66.0
    if birth_year <= 1959:
        return 66 + (birth_year - 1954) * 2 / 12
    return 67.0


def worker_claim_factor(claim_age: float, fra: float) -> float:
    """Share of the PIA paid when claiming at ``claim_age`` (before or after FRA)."""
    months = round((fra - claim_age) * 12)
    if months <= 0:
        return 1 + min(-months, (70 - fra) * 12) * (2 / 3) / 100  # 8%/yr credit
    first = min(months, 36)
    return 1 - first * (5 / 9) / 100 - max(months - 36, 0) * (5 / 12) / 100


def spouse_claim_factor(claim_age: float, fra: float) -> float:
    """Spousal benefit as a share of the worker's PIA."""
    months = max(round((fra - claim_age) * 12), 0)
    first = min(months, 36)
    reduction = first * (25 / 36) / 100 + max(months - 36, 0) * (5 / 12) / 100
    return 0.5 * (1 - reduction)


def _ref_series(name: str, col: str) -> pd.Series:
    df = data.reference(name).set_index("year")[col].astype(float)
    return df


def retired_spending(costs: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Annual retired-couple spending before and after Medicare, year-t dollars."""
    r = cfg["retirement"]
    ay = cfg["model"]["anchor_year"]
    goods = ["appliances", "furnishings", "communications", "tv_and_cable", "apparel",
             "personal_care", "household_supplies", "entertainment", "miscellaneous"]
    cars = ["car_depreciation", "car_fuel", "car_insurance", "car_maintenance", "car_fees"]
    core = (costs[["property_tax", "home_insurance", "home_maintenance", "utilities"]].sum(axis=1)
            + costs[cars].sum(axis=1)
            + r["couple_share_food"] * costs[["groceries", "restaurants"]].sum(axis=1)
            + r["couple_share_goods"] * costs[goods].sum(axis=1)
            + r["couple_share_food"] * costs[["vacation_domestic", "vacation_international"]].sum(axis=1)
            + r["couple_share_food"] * costs["health_out_of_pocket"])
    pre_medicare = r["pre_medicare_premium_share"] * costs["health_total_premium"]
    medicare = 2 * r["medicare_costs_per_person_anchor"] * data.price_index("MEDICAL", ay).reindex(costs.index)
    return pd.DataFrame({"core": core, "health_pre65": pre_medicare, "health_65plus": medicare})


def plan_horizon(years: pd.Index, cfg: dict) -> pd.Series:
    """Age to plan to: the longer-lived spouse's life expectancy at 65, plus a buffer."""
    le = data.reference("life_expectancy").set_index("year")
    longest = le[["male_65", "female_65"]].max(axis=1).astype(float)
    longest = longest.reindex(range(min(years.min(), longest.index.min()), years.max() + 1))
    longest = longest.interpolate(limit_direction="both")
    return (65 + longest + cfg["retirement"]["longevity_buffer_years"]).reindex(years)


def savings_required(costs: pd.DataFrame, incomes: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Annual retirement saving needed, by year and scenario ("A" two earners, "B" one)."""
    r, hh = cfg["retirement"], cfg["household"]
    years = costs.index
    spend = retired_spending(costs, cfg)
    horizon = plan_horizon(years, cfg)
    db = _ref_series("db_pension", "db_share").reindex(
        range(min(years.min(), 1975), years.max() + 1)).interpolate(limit_direction="both").reindex(years)
    earnings = incomes["median_ft_earnings"].reindex(years)

    rows = []
    for y in years:
        birth = y - hh["parent_age"]
        fra = full_retirement_age(birth)
        claim = r["ss_claim_age"]
        pia = r["ss_pia_replacement"] * earnings[y]
        ages = np.arange(r["retire_age"], horizon[y], 1.0)
        disc = (1 + r["real_return_retirement"]) ** -(ages - r["retire_age"])
        n_save = r["retire_age"] - r["start_saving_age"]
        annuity = ((1 + r["real_return_accumulation"]) ** n_save - 1) / r["real_return_accumulation"]
        for scen, earners in (("A", 2), ("B", 1)):
            if earners == 2:
                ss = 2 * pia * worker_claim_factor(claim, fra)
            else:
                ss = pia * (worker_claim_factor(claim, fra) + spouse_claim_factor(claim, fra))
            pension = db[y] * r["db_pension_replacement"] * earnings[y] * earners
            need = (spend.at[y, "core"]
                    + np.where(ages < 65, spend.at[y, "health_pre65"], spend.at[y, "health_65plus"])
                    - np.where(ages >= claim, ss + pension, 0.0))
            nest_egg = float(np.sum(np.maximum(need, 0) * disc))
            rows.append({"year": y, "scenario": scen, "nest_egg": nest_egg,
                         "retirement_saving": nest_egg / annuity,
                         "ss_benefit": ss, "pension": pension, "fra": fra,
                         "plan_to_age": horizon[y],
                         "retired_core_spending": spend.at[y, "core"]})
    return pd.DataFrame(rows).set_index(["year", "scenario"])
