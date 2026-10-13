"""Run an American Dream Index household through a YNAB-style budget.

The index says what the lifestyle costs per year. This module asks the
envelope-budgeting question instead: if a family earning a given income
gives every dollar a job, month by month, which parts of the lifestyle get
funded and which go without?

For one index year and scenario it builds a 12-month ``Plan``:

* one category per index line item (``components.CATEGORY``), grouped like
  the index, each with the target a careful budgeter would set for that
  kind of bill (monthly bill, refill-up-to spending, an annual or
  semi-annual bill due on a date, or a sinking fund);
* biweekly take-home pay: the chosen gross income minus federal, state and
  FICA tax interpolated from the index's TAXSIM grid;
* everyday spending on a credit card paid off in full each month, bills
  from checking, retirement saving moved to an off-budget 401(k);
* each month, income is assigned to underfunded targets in priority order
  (obligations before flexible spending before saving);
* a warm-up year runs first with the same amounts, so sinking funds,
  buffers from three-paycheck months and Age of Money start the reported
  year in a steady state rather than at zero.

Bills are paid whether or not they were funded (overspending comes out of
next month's Ready to Assign, as in YNAB). Flexible spending and saving are
cut back to what is available: the shortfall is what the family goes
without.

Amounts are nominal dollars of the chosen year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import money
from .engine import READY_TO_ASSIGN, Plan
from .targets import Target

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"


@dataclass(frozen=True)
class Line:
    """How a line item behaves in the budget."""
    name: str
    group: str
    kind: str            # bill | flex | annual | sinking | saving
    paid_with: str = "Checking"
    due_months: tuple[int, ...] = ()   # annual/semiannual bills and sinking-fund spends
    day: int = 1


# Priority order: YNAB's "obligations first", then true expenses, then
# flexible spending, then goals.
LINES = [
    Line("mortgage_payment", "Housing", "bill", day=1),
    Line("utilities", "Housing", "bill", day=20),
    Line("childcare", "Childcare", "bill", day=1),
    Line("health_premium", "Healthcare", "bill", day=1),
    Line("car_finance", "Transportation", "bill", day=10),
    Line("communications", "Technology", "bill", "Visa", day=15),
    Line("tv_and_cable", "Technology", "bill", "Visa", day=15),
    Line("property_tax", "Housing", "annual", due_months=(4, 10), day=10),
    Line("home_insurance", "Housing", "annual", due_months=(3,), day=5),
    Line("car_insurance", "Transportation", "annual", due_months=(1, 7), day=5),
    Line("car_fees", "Transportation", "annual", due_months=(5,), day=5),
    Line("groceries", "Food", "flex", "Visa"),
    Line("car_fuel", "Transportation", "flex", "Visa"),
    Line("household_supplies", "Other necessities", "flex", "Visa"),
    Line("personal_care", "Other necessities", "flex", "Visa"),
    Line("health_out_of_pocket", "Healthcare", "sinking", "Visa", due_months=(3, 6, 9, 12)),
    Line("home_maintenance", "Housing", "sinking", "Visa", due_months=(4, 8, 12)),
    Line("car_maintenance", "Transportation", "sinking", "Visa", due_months=(4, 8, 12)),
    Line("apparel", "Other necessities", "sinking", "Visa", due_months=(4, 8, 12)),
    Line("restaurants", "Food", "flex", "Visa"),
    Line("entertainment", "Other necessities", "flex", "Visa"),
    Line("miscellaneous", "Other necessities", "flex", "Visa"),
    Line("appliances", "Household goods", "sinking", "Visa", due_months=(11,)),
    Line("furnishings", "Household goods", "sinking", "Visa", due_months=(6,)),
    Line("vacation_domestic", "Vacations", "sinking", "Visa", due_months=(7,)),
    Line("vacation_international", "Vacations", "saving"),
    Line("car_depreciation", "Transportation", "saving"),
    Line("down_payment_saving", "Housing", "saving"),
    Line("retirement_saving", "Retirement saving", "saving"),
]
FLEX_SPEND_DAYS = (7, 14, 21, 28)


def label(item: str) -> str:
    return item.replace("_", " ").capitalize()


def take_home(gross: float, year: int, scenario: str, grid: pd.DataFrame | None = None) -> float:
    """Gross income minus income and payroll taxes, from the TAXSIM grid."""
    grid = pd.read_csv(PROCESSED / "tax_grid.csv") if grid is None else grid
    g = grid[(grid.year == year) & (grid.scenario == scenario)].sort_values("gross")
    if g.empty:
        raise ValueError(f"no tax grid for {year} {scenario}")
    return gross - float(np.interp(gross, g["gross"], g["total"]))


def annual_amounts(year: int, scenario: str) -> dict[str, float]:
    costs = pd.read_csv(PROCESSED / "costs.csv", index_col=0)
    summary = pd.read_csv(PROCESSED / "summary.csv")
    row = summary[(summary.year == year) & (summary.scenario == scenario)]
    if row.empty:
        raise ValueError(f"no index results for {year} {scenario}")
    out = {ln.name: float(costs.loc[year, ln.name]) for ln in LINES if ln.name in costs.columns}
    out["retirement_saving"] = float(row["cat: Retirement saving"].iloc[0])
    if scenario != "A":
        out.pop("childcare")
    return out


def target_for(line: Line, annual: int, year: int) -> Target:
    if line.kind in ("bill", "flex"):
        return Target("NEED", annual // 12, whole_amount=False)
    if line.kind == "annual":
        per = annual // len(line.due_months)
        cadence = 12 // len(line.due_months)
        return Target("NEED", per, target_date=date(year, line.due_months[0], 1),
                      whole_amount=True, cadence_months=cadence)
    return Target("MF", annual // 12)


def build_plan(year: int, scenario: str = "A", gross: float | None = None,
               opening_cash: float = 0.0) -> tuple[Plan, dict]:
    """Build and run the 12-month plan. ``gross`` defaults to median married-couple income."""
    summary = pd.read_csv(PROCESSED / "summary.csv")
    row = summary[(summary.year == year) & (summary.scenario == scenario)].iloc[0]
    gross = float(row["median_married_couple"]) if gross is None else gross
    net = take_home(gross, year, scenario)
    amounts = annual_amounts(year, scenario)
    lines = [ln for ln in LINES if ln.name in amounts]

    p = Plan(f"American Dream {year} {scenario}")
    start = date(year - 1, 1, 1)
    p.add_account("Checking", balance=money.to_milli(opening_cash) if opening_cash else 0,
                  opened=start)
    p.add_account("Visa", credit=True)
    p.add_account("401(k)", on_budget=False)
    for ln in lines:
        p.add_category(label(ln.name), ln.group,
                       target=target_for(ln, money.to_milli(amounts[ln.name]), year - 1))
    visa = p.categories.pop("Visa")       # pay the card before anything else
    p.categories = {"Visa": visa, **p.categories}

    # Biweekly paychecks from the first Friday of the warm-up year.
    paycheck = money.to_milli(net / 26)
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    while d.year <= year:
        p.add_transaction(d, "Checking", paycheck, READY_TO_ASSIGN, "Paycheck")
        d += timedelta(days=14)

    planned: dict[str, int] = {}
    for y in (year - 1, year):
        tally = planned if y == year else {}
        for month in range(1, 13):
            _run_month(p, lines, amounts, date(y, month, 1), tally)

    meta = {"year": year, "scenario": scenario, "gross": gross, "take_home": net,
            "required_gross": float(row["cost_pretax"]), "planned": planned,
            "amounts": amounts, "lines": lines}
    return p, meta


def _run_month(p: Plan, lines: list[Line], amounts: dict[str, float], m: date,
               planned: dict[str, int]) -> None:
    p.auto_assign_underfunded(m)
    for ln in lines:
        cat = label(ln.name)
        annual = money.to_milli(amounts[ln.name])
        if ln.kind == "bill":
            _spend(p, m.replace(day=ln.day), ln.paid_with, cat, annual // 12, planned, cap=False)
        elif ln.kind == "annual" and m.month in ln.due_months:
            _spend(p, m.replace(day=ln.day), ln.paid_with, cat,
                   annual // len(ln.due_months), planned, cap=False)
        elif ln.kind == "flex":
            each = annual // 12 // len(FLEX_SPEND_DAYS)
            for day in FLEX_SPEND_DAYS:
                _spend(p, m.replace(day=day), ln.paid_with, cat, each, planned, cap=True)
        elif ln.kind == "sinking" and m.month in ln.due_months:
            _spend(p, m.replace(day=25), ln.paid_with, cat,
                   annual // len(ln.due_months), planned, cap=True)
        elif ln.name == "retirement_saving":
            want = annual // 12
            have = max(0, p.compute(m)[m].categories[cat].available)
            planned[cat] = planned.get(cat, 0) + want
            if min(want, have) > 0:
                p.transfer(m.replace(day=28), "Checking", "401(k)", min(want, have), category=cat)
    # Pay the card statement from its payment category (in full when funded).
    owed = p.compute(m)[m].categories["Visa"].available
    if owed > 0:
        p.transfer(m.replace(day=27), "Checking", "Visa", owed)


def _spend(p: Plan, when: date, account: str, cat: str, amount: int,
           planned: dict[str, int], cap: bool) -> None:
    planned[cat] = planned.get(cat, 0) + amount
    if cap:
        m = date(when.year, when.month, 1)
        amount = min(amount, max(0, p.compute(m)[m].categories[cat].available))
    if amount > 0:
        p.add_transaction(when, account, -amount, cat)


def report(p: Plan, meta: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-category annual results and per-month plan totals (in dollars)."""
    year = meta["year"]
    views = {m: v for m, v in p.compute(date(year, 12, 1)).items() if m.year == year}
    dec = date(year, 12, 1)
    rows = []
    for ln in meta["lines"]:
        cat = label(ln.name)
        assigned = sum(views[m].categories[cat].assigned for m in views)
        spent = -sum(views[m].categories[cat].activity for m in views)
        planned = meta["planned"].get(cat, 0)
        if ln.kind == "saving":
            saved = assigned if ln.name != "retirement_saving" else spent
            planned, spent = money.to_milli(meta["amounts"][ln.name]), saved
        rows.append({
            "category": cat, "group": ln.group, "kind": ln.kind,
            "annual_cost": meta["amounts"][ln.name],
            "assigned": money.to_currency(assigned),
            "spent_or_saved": money.to_currency(spent),
            "shortfall": money.to_currency(max(0, planned - spent)),
            "cash_overspent": money.to_currency(sum(views[m].categories[cat].cash_overspent for m in views)),
            "available_dec": money.to_currency(views[dec].categories[cat].available),
        })
    cats = pd.DataFrame(rows)
    cats["funded_share"] = (1 - cats["shortfall"] / cats["annual_cost"]).clip(0, 1).round(3)
    months = pd.DataFrame([{
        "month": m.isoformat()[:7],
        "income": money.to_currency(v.income),
        "assigned": money.to_currency(v.assigned),
        "activity": money.to_currency(v.activity),
        "ready_to_assign": money.to_currency(v.to_be_budgeted),
        "underfunded": money.to_currency(sum((r.goal or {}).get("goal_under_funded", 0)
                                             for r in v.categories.values())),
        "age_of_money": v.age_of_money,
    } for m, v in views.items()])
    return cats, months


def run(year: int, scenario: str = "A", gross: float | None = None,
        out_dir: Path | str = PROCESSED) -> dict:
    p, meta = build_plan(year, scenario, gross)
    cats, months = report(p, meta)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"budget_{year}_{scenario}"
    cats.to_csv(out_dir / f"{stem}_categories.csv", index=False)
    months.to_csv(out_dir / f"{stem}_months.csv", index=False)
    return {"plan": p, "meta": meta, "categories": cats, "months": months}
