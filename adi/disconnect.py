"""Why the index says "cheaper" when most people feel "more expensive".

Quantifies the gap between the index and common perception along four lines:

1. **The yardstick**: the same cost against different income benchmarks.
2. **Earnings per family vs. per worker**: how much of the improvement comes
   from married couples bringing in more paychecks rather than the lifestyle
   costing fewer paychecks.
3. **What got dearer and what got cheaper**: the change in each category,
   measured in median full-time paychecks.
4. **Assumptions**: how the 1980-2025 change moves under alternative choices
   (constant-quality basket, market interest rates, payable Social Security,
   actual new-home prices, higher out-of-pocket health costs).

Run with ``python -m adi disconnect``; writes data/processed/disconnect_*.csv
and charts 05-06.
"""

from __future__ import annotations

import copy
from pathlib import Path

import numpy as np
import pandas as pd

from . import components, data, index

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed"
YEARS = [1980, 1985, 1990, 2000, 2010, 2019, 2021, 2025]

BENCHMARKS = {
    "median_ft_earnings": "One full-time paycheck (BLS median)",
    "median_household": "Median household (Census H-5)",
    "median_married_couple": "Median married couple (F-7)",
    "median_married_with_children": "Median married couple with children (F-10)",
    "median_family_two_earners": "Median two-earner family (F-12)",
    "median_family_one_earner": "Median one-earner family (F-12)",
    "median_family_head_25_34": "Median family, householder 25-34 (F-11)",
    "median_family_head_35_44": "Median family, householder 35-44 (F-11)",
}

CONSTANT_BASKET = {
    ("household_goods", "furnishings_index"): "FURNITURE",
    ("other", "apparel_index"): "APPAREL",
    ("other", "personal_care_index"): "PERSONAL_CARE",
    ("other", "household_supplies_index"): "HOUSEHOLD_SUPPLIES",
    ("other", "entertainment_index"): "ENTERTAINMENT",
    ("other", "miscellaneous_index"): "CPI_ALL",
    ("technology", "communications_index"): "WIRELESS",
    ("transportation", "total_per_car"): None,
}
ITEM_CPI = {"television_60in": "TV", "refrigerator": "MAJOR_APPLIANCES", "freezer": "MAJOR_APPLIANCES",
            "washer": "LAUNDRY", "dryer": "LAUNDRY", "microwave": "OTHER_APPLIANCES",
            "range_oven": "MAJOR_APPLIANCES"}

VARIANTS = {
    "Baseline": {},
    "Constant-quality basket (item CPIs, CPI new cars)": CONSTANT_BASKET,
    "Market interest rates for retirement returns": {("retirement", "real_return_accumulation"): "market"},
    "Social Security at payable level after 2033": {("retirement", "ss_payable_share"): 0.77},
    "Actual median new-home prices (homes grow)": {("housing", "price_index"): "MEDIAN_NEW_HOME"},
    "Out-of-pocket health at Milliman level": {("healthcare", "out_of_pocket_anchor"): 4870},
}
VARIANTS["All four pessimistic choices"] = {
    k: v for name, ov in list(VARIANTS.items())[2:] for k, v in ov.items()}


def _apply(cfg: dict, overrides: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    for (section, key), value in overrides.items():
        if value is None:
            cfg[section].pop(key, None)
        else:
            cfg[section][key] = value
    if overrides is CONSTANT_BASKET:
        for item, idx in ITEM_CPI.items():
            cfg["household_goods"]["items"][item]["index"] = idx
    return cfg


def benchmarks(summary: pd.DataFrame, inc: pd.DataFrame) -> pd.DataFrame:
    """Cost as a multiple of each benchmark income, selected years."""
    rows = []
    for scen in ("A", "B"):
        cost = summary[summary.scenario == scen].set_index("year")["cost_pretax"]
        for col, label in BENCHMARKS.items():
            if (scen == "A" and col == "median_family_one_earner") or (
                    scen == "B" and col == "median_family_two_earners"):
                continue
            ratio = cost / inc[col].reindex(cost.index)
            rows.append({"scenario": scen, "benchmark": label, **{y: ratio[y] for y in YEARS},
                         "change_1980_2025": ratio[2025] / ratio[1980] - 1,
                         "change_1990_2025": ratio[2025] / ratio[1990] - 1,
                         "change_2019_2025": ratio[2025] / ratio[2019] - 1,
                         "income_growth_1980_2025": inc[col][2025] / inc[col][1980]})
    return pd.DataFrame(rows)


def paychecks_per_couple(inc: pd.DataFrame) -> pd.DataFrame:
    """Married-couple income measured in full-time paychecks."""
    e = inc["median_ft_earnings"]
    return pd.DataFrame({
        "married_couple": inc["median_married_couple"] / e,
        "married_with_children": inc["median_married_with_children"] / e,
        "household": inc["median_household"] / e,
    }).dropna()


def ratio_decomposition(summary: pd.DataFrame, inc: pd.DataFrame, start: int, end: int) -> dict:
    """Split the change in cost / married-couple income into
    (cost / paycheck) x (paychecks per couple), in log points."""
    a = summary[summary.scenario == "A"].set_index("year")
    e = inc["median_ft_earnings"]
    ratio = a["cost_pretax"] / inc["median_married_couple"]
    per_paycheck = a["cost_pretax"] / e
    couple = inc["median_married_couple"] / e
    total = np.log(ratio[end] / ratio[start])
    return {
        "start": start, "end": end,
        "ratio_start": ratio[start], "ratio_end": ratio[end],
        "log_change_total": total,
        "log_change_cost_per_paycheck": np.log(per_paycheck[end] / per_paycheck[start]),
        "log_change_paychecks_per_couple": -np.log(couple[end] / couple[start]),
        "share_from_couples_earning_more": -np.log(couple[end] / couple[start]) / total,
    }


def category_paychecks(summary: pd.DataFrame, inc: pd.DataFrame, scen: str = "A") -> pd.DataFrame:
    """Each category's cost in full-time median paychecks, and its change."""
    s = summary[summary.scenario == scen].set_index("year")
    cats = [c for c in s.columns if c.startswith("cat: ")]
    pay = s[cats].div(inc["median_ft_earnings"].reindex(s.index), axis=0)
    pay.columns = [c[5:] for c in cats]
    out = pay.loc[[1980, 1990, 2000, 2019, 2025]].T
    out["change_1980_2025"] = out[2025] - out[1980]
    out["change_2019_2025"] = out[2025] - out[2019]
    out.loc["Total"] = out.sum()
    return out


def housing_sticker_vs_payment(costs: pd.DataFrame, inc: pd.DataFrame) -> pd.DataFrame:
    """House price-to-income (what people quote) vs. payment-to-income (what they pay)."""
    y = costs.index
    mc, hh = inc["median_married_couple"].reindex(y), inc["median_household"].reindex(y)
    out = pd.DataFrame({
        "home_price": costs["home_price"],
        "mortgage_rate": costs["mortgage_rate"],
        "price_to_household_income": costs["home_price"] / hh,
        "price_to_married_couple_income": costs["home_price"] / mc,
        "payment_to_household_income": costs["mortgage_payment"] / hh,
        "payment_to_married_couple_income": costs["mortgage_payment"] / mc,
    })
    return out.loc[[1980, 1985, 1990, 2000, 2006, 2012, 2019, 2021, 2025]]


def variants(cfg: dict) -> pd.DataFrame:
    rows = []
    inc = data.incomes()
    for name, overrides in VARIANTS.items():
        res = index.build(_apply(cfg, overrides))
        a = res["summary"][res["summary"].scenario == "A"].set_index("year")
        ratio = a["cost_pretax"] / a["median_married_couple"]
        pay = a["earners_needed"]
        rows.append({"variant": name,
                     "share_1980": ratio[1980], "share_2019": ratio[2019], "share_2025": ratio[2025],
                     "share_change_1980_2025": ratio[2025] / ratio[1980] - 1,
                     "paychecks_1980": pay[1980], "paychecks_2019": pay[2019], "paychecks_2025": pay[2025],
                     "paychecks_change_1980_2025": pay[2025] / pay[1980] - 1,
                     "vs_married_with_children_change": (a["cost_pretax"][2025] / inc["median_married_with_children"][2025])
                     / (a["cost_pretax"][1980] / inc["median_married_with_children"][1980]) - 1})
    return pd.DataFrame(rows)


def run(cfg: dict | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or index.load_config()
    res = index.build(cfg)
    inc = data.incomes()
    summary = res["summary"]
    out = {
        "benchmarks": benchmarks(summary, inc),
        "paychecks_per_couple": paychecks_per_couple(inc).loc[YEARS],
        "decomposition": pd.DataFrame([ratio_decomposition(summary, inc, s, 2025)
                                       for s in (1980, 1985, 1990, 2000, 2019, 2021)]),
        "category_paychecks": category_paychecks(summary, inc),
        "housing": housing_sticker_vs_payment(res["costs"], inc),
        "household_mix": data.household_mix().loc[[1980, 1990, 2000, 2010, 2019, 2025]],
        "variants": variants(cfg),
    }
    from . import charts
    out["_charts"] = charts.yardsticks(summary, inc) + charts.paycheck_changes(out["category_paychecks"])
    OUT.mkdir(parents=True, exist_ok=True)
    for name, df in out.items():
        if name.startswith("_"):
            continue
        df.round(4).to_csv(OUT / f"disconnect_{name}.csv", index=name not in {"benchmarks", "decomposition", "variants"})
    return out
