"""Export model results for the interactive web page (web/index.html).

The page recomputes housing, childcare and retirement in the browser when the
reader moves a slider, so the export carries the per-year inputs those pieces
need, plus each year's TAXSIM tax schedule so the gross-up can be redone by
interpolation (holding itemized deductions at their baseline values).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import components, data, retirement

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def payload(results: dict[str, pd.DataFrame], cfg: dict) -> dict:
    costs = results["costs"]
    summary = results["summary"]
    ret = results["retirement"]
    grid = results["tax_grid"]
    years = [int(y) for y in costs.index]
    r, h = cfg["retirement"], cfg["housing"]
    spend = retirement.retired_spending(costs, cfg)
    db = data.reference("db_pension").set_index("year")["db_share"].astype(float)
    db = db.reindex(range(min(years[0], int(db.index.min())), years[-1] + 1)).interpolate(
        limit_direction="both").reindex(years)

    def col(df, name, digits=0):
        return [round(float(v), digits) for v in df[name]]

    per_year = {
        "year": years,
        "cpi": col(results["cpi"], "cpi", 5),
        "home_price": col(costs, "home_price"),
        "mortgage_rate": col(costs, "mortgage_rate", 3),
        "median_household": col(summary[summary.scenario == "A"], "median_household"),
        "median_married_couple": col(summary[summary.scenario == "A"], "median_married_couple"),
        "median_ft_earnings": col(summary[summary.scenario == "A"], "median_ft_earnings"),
        "retired_core": col(spend, "core"),
        "health_pre65": col(spend, "health_pre65"),
        "health_65plus": col(spend, "health_65plus"),
        "plan_to_age": col(ret[ret.scenario == "A"], "plan_to_age", 2),
        "ss_A": col(ret[ret.scenario == "A"], "ss_benefit"),
        "ss_B": col(ret[ret.scenario == "B"], "ss_benefit"),
        "db_share": [round(float(v), 4) for v in db],
        "items": {c: col(costs, c) for c in components.CATEGORY},
    }
    tax = {}
    for scen in ("A", "B"):
        g = grid[grid.scenario == scen]
        tax[scen] = {str(y): {"gross": col(gy.sort_values("gross"), "gross"),
                              "tax": col(gy.sort_values("gross"), "total")}
                     for y, gy in g.groupby("year")}
    return {
        "per_year": per_year,
        "category": components.CATEGORY,
        "tax": tax,
        "baseline": {scen: {
            "cost_pretax": col(summary[summary.scenario == scen], "cost_pretax"),
            "retirement_saving": col(ret[ret.scenario == scen], "retirement_saving"),
        } for scen in ("A", "B")},
        "assumptions": {
            "retire_age": r["retire_age"],
            "start_saving_age": r["start_saving_age"],
            "ss_claim_age": r["ss_claim_age"],
            "real_return_accumulation": r["real_return_accumulation"],
            "real_return_retirement": r["real_return_retirement"],
            "db_pension_replacement": r["db_pension_replacement"],
            "down_payment": h["down_payment"],
            "down_payment_save_years": h["down_payment_save_years"],
            "mortgage_term_years": h["mortgage_term_years"],
            "property_tax_rate": h["property_tax_rate"],
            "maintenance_rate": h["maintenance_rate"],
        },
    }


def export(results: dict[str, pd.DataFrame], cfg: dict) -> Path:
    WEB.mkdir(exist_ok=True)
    data_json = json.dumps(payload(results, cfg), separators=(",", ":"))
    (WEB / "adi_data.json").write_text(data_json)
    template = (WEB / "template.html").read_text()
    out = WEB / "index.html"
    out.write_text(template.replace("/*__ADI_DATA__*/null", data_json))
    return out
