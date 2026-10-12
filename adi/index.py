"""Assemble the American Dream Index from components, retirement and taxes.

Scenarios
---------
A  Two earners. Both children in paid full-time care.
B  One earner. A parent cares for the children at home (no childcare bill),
   and Social Security includes a spousal benefit.

For each year the index reports the *pre-tax income* needed to fund the
lifestyle (spending + retirement saving + income and payroll taxes), and
compares it with median household income, median married-couple family
income, and median full-time earnings.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pandas as pd

from . import components, data, retirement, taxes

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "assumptions.toml"
SCENARIOS = {"A": "Two earners, paid childcare", "B": "One earner, parent at home"}


def load_config(path: Path | str = DEFAULT_CONFIG) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def build(cfg: dict | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or load_config()
    costs = components.build(cfg)
    inc = data.incomes().reindex(costs.index)
    ret = retirement.savings_required(costs, inc, cfg)

    living = {}
    households = []
    for scen in SCENARIOS:
        items = [c for c in components.CATEGORY if scen == "A" or c != "childcare"]
        cat = components.by_category(costs, items)
        cat["Retirement saving"] = ret.xs(scen, level="scenario")["retirement_saving"]
        living[scen] = cat
        h = pd.DataFrame({
            "spending": cat.sum(axis=1),
            "base": inc["median_married_couple"],
            "earners": 2 if scen == "A" else 1,
            "mortgage_interest": costs["mortgage_interest"],
            "property_tax": costs["property_tax"],
            "childcare": costs["childcare"] if scen == "A" else 0.0,
        })
        h["scenario"] = scen
        households.append(h.reset_index().set_index(["year", "scenario"]))
    households = pd.concat(households).sort_index()

    grid = taxes.tax_grid(households, cfg)
    gross = taxes.required_gross(households, grid)

    summary = []
    for scen in SCENARIOS:
        g = gross.xs(scen, level="scenario")
        cat = living[scen].copy()
        cat["Taxes"] = g["federal"] + g["state"] + g["fica"]
        total = g["gross_required"]
        s = pd.DataFrame({
            "scenario": scen,
            "cost_pretax": total,
            "spending_after_tax": living[scen].sum(axis=1),
            "federal_tax": g["federal"], "state_tax": g["state"], "fica": g["fica"],
            "median_household": inc["median_household"],
            "median_married_couple": inc["median_married_couple"],
            "median_ft_earnings": inc["median_ft_earnings"],
        })
        s["pct_of_household_income"] = total / s["median_household"]
        s["pct_of_married_couple_income"] = total / s["median_married_couple"]
        s["earners_needed"] = total / s["median_ft_earnings"]
        s = pd.concat([s, cat.add_prefix("cat: ")], axis=1)
        summary.append(s.reset_index())
    summary = pd.concat(summary, ignore_index=True)

    cpi = data.price_index("CPI_ALL", cfg["model"]["end_year"]).reindex(costs.index)
    return {
        "summary": summary,
        "costs": costs,
        "retirement": ret.reset_index(),
        "tax_grid": grid,
        "cpi": cpi.rename("cpi").to_frame(),
    }


def save(results: dict[str, pd.DataFrame], out_dir: Path | str = ROOT / "data" / "processed") -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, df in results.items():
        df.round(4).to_csv(out_dir / f"{name}.csv", index=name in {"costs", "cpi"})
