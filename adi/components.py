"""Annual cost of each piece of the American Dream lifestyle, in nominal dollars.

Each line item is either
* priced from its own historical series (house prices, mortgage rates,
  KFF health premiums, auto loan rates), or
* an anchor-year dollar amount carried to other years on a price index
  (``data.PRICE_INDEXES``).

The result is a DataFrame indexed by year with one column per line item;
``CATEGORY`` maps each line item to the chart category it rolls up into.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data

CATEGORY = {
    "mortgage_payment": "Housing",
    "down_payment_saving": "Housing",
    "property_tax": "Housing",
    "home_insurance": "Housing",
    "home_maintenance": "Housing",
    "utilities": "Housing",
    "car_depreciation": "Transportation",
    "car_finance": "Transportation",
    "car_fuel": "Transportation",
    "car_insurance": "Transportation",
    "car_maintenance": "Transportation",
    "car_fees": "Transportation",
    "childcare": "Childcare",
    "groceries": "Food",
    "restaurants": "Food",
    "appliances": "Household goods",
    "furnishings": "Household goods",
    "communications": "Technology",
    "tv_and_cable": "Technology",
    "health_premium": "Healthcare",
    "health_out_of_pocket": "Healthcare",
    "vacation_domestic": "Vacations",
    "vacation_international": "Vacations",
    "apparel": "Other necessities",
    "personal_care": "Other necessities",
    "household_supplies": "Other necessities",
    "entertainment": "Other necessities",
    "miscellaneous": "Other necessities",
}


def mortgage_payment(principal: float | np.ndarray, rate_pct, years: int = 30):
    """Annual principal & interest on a fixed-rate, monthly-pay mortgage."""
    r = np.asarray(rate_pct, dtype=float) / 1200
    n = years * 12
    return principal * r / (1 - (1 + r) ** -n) * 12


def average_interest(principal, rate_pct, years: int, first_years: int):
    """Average annual interest paid over the first ``first_years`` of the loan."""
    r = np.asarray(rate_pct, dtype=float) / 1200
    n, k = years * 12, first_years * 12
    pmt = principal * r / (1 - (1 + r) ** -n)
    balance_k = principal * (1 + r) ** k - pmt * ((1 + r) ** k - 1) / r
    total_paid = pmt * k
    principal_repaid = principal - balance_k
    return (total_paid - principal_repaid) / first_years


def _carry(anchor: float, index: str, years: pd.Index, anchor_year: int) -> pd.Series:
    return anchor * data.price_index(index, anchor_year).reindex(years)


def anchor_value(spec, anchor_year: int) -> float:
    """An anchor is a number, or ``"ce:ITEM"`` / ``"ce:ITEM-ITEM2"`` from the CE survey."""
    if isinstance(spec, (int, float)):
        return float(spec)
    kind, expr = spec.split(":", 1)
    if kind != "ce":
        raise ValueError(f"unknown anchor source {spec!r}")
    total = 0.0
    for sign, item in _terms(expr):
        total += sign * data.ce(item)[anchor_year]
    return total


def _terms(expr: str):
    sign, buf = 1, ""
    for ch in expr + "+":
        if ch in "+-":
            if buf:
                yield sign, buf.strip()
            sign, buf = (1 if ch == "+" else -1), ""
        else:
            buf += ch


def housing(cfg: dict, years: pd.Index) -> pd.DataFrame:
    h, ay = cfg["housing"], cfg["model"]["anchor_year"]
    # Default: FHFA repeat-sales index (constant quality). "MEDIAN_NEW_HOME"
    # follows the median price of new houses sold instead, so homes get
    # bigger and better over time as they actually did.
    series = data.fred("median_new_home" if h.get("price_index") == "MEDIAN_NEW_HOME" else "hpi")
    price = h["anchor_price"] * series.reindex(years) / series[ay]
    rate = data.fred("mortgage_rate").reindex(years)
    loan = price * (1 - h["down_payment"])
    out = pd.DataFrame(index=years)
    out["home_price"] = price
    out["mortgage_rate"] = rate
    out["mortgage_payment"] = mortgage_payment(loan, rate, h["mortgage_term_years"])
    out["mortgage_interest"] = average_interest(
        loan, rate, h["mortgage_term_years"], h["interest_averaging_years"])
    out["down_payment_saving"] = price * h["down_payment"] / h["down_payment_save_years"]
    out["property_tax_rate"] = _rate_series(h["property_tax_rate"], years)
    out["property_tax"] = price * out["property_tax_rate"]
    out["home_insurance"] = home_insurance(h, years, ay)
    out["home_maintenance"] = price * h["maintenance_rate"]
    out["utilities"] = _carry(anchor_value(h["utilities_anchor"], ay), "UTILITIES", years, ay)
    return out


def _rate_series(spec, years: pd.Index) -> pd.Series:
    """A constant rate, or ``"reference:NAME"`` interpolated from data/reference."""
    if isinstance(spec, (int, float)):
        return pd.Series(float(spec), index=years)
    ref = data.reference(spec.split(":", 1)[1]).set_index("year")["rate"].astype(float)
    full = ref.reindex(range(min(ref.index.min(), years.min()), max(ref.index.max(), years.max()) + 1))
    return full.interpolate(limit_direction="both").reindex(years)


def home_insurance(h: dict, years: pd.Index, ay: int) -> pd.Series:
    """NAIC average HO-3 premium where published, extended on the insurance CPI."""
    if h["insurance_anchor"] != "reference:home_insurance":
        return _carry(anchor_value(h["insurance_anchor"], ay), "HOME_INSURANCE", years, ay)
    naic = data.reference("home_insurance").set_index("year")["ho3_premium"].astype(float)
    return data.splice([naic, data.price_index("HOME_INSURANCE", ay)]).reindex(years)


def _loan_cost_factor(rate_pct, months: int = 60) -> np.ndarray:
    """Total interest per dollar borrowed over the life of an amortizing loan."""
    r = np.asarray(rate_pct, dtype=float) / 1200
    return months * r / (1 - (1 + r) ** -months) - 1


def transportation(cfg: dict, years: pd.Index) -> pd.DataFrame:
    t, ay = cfg["transportation"], cfg["model"]["anchor_year"]
    n = t["cars"]
    out = pd.DataFrame(index=years)
    out["car_depreciation"] = n * _carry(t["depreciation_anchor"], t.get("depreciation_index", "NEW_VEHICLES"), years, ay)
    rate = data.fred("auto_loan_rate").reindex(years).interpolate(limit_direction="both")
    rate_effect = _loan_cost_factor(rate) / _loan_cost_factor(data.fred("auto_loan_rate")[ay])
    out["car_finance"] = n * _carry(t["finance_anchor"], t.get("depreciation_index", "NEW_VEHICLES"), years, ay) * rate_effect
    out["car_fuel"] = n * _carry(t["fuel_anchor"], "GASOLINE", years, ay)
    out["car_insurance"] = n * _carry(t["insurance_anchor"], "AUTO_INSURANCE", years, ay)
    out["car_maintenance"] = n * _carry(t["maintenance_anchor"], "AUTO_MAINTENANCE", years, ay)
    out["car_fees"] = n * _carry(t["fees_anchor"], "AUTO_FEES", years, ay)
    if t.get("total_per_car") == "reference:aaa_driving_costs":
        # Scale the components so they sum to AAA's published total for the
        # year: the CPI pieces set the mix, AAA sets the level.
        aaa = data.reference("aaa_driving_costs").set_index("year")["total_per_car"].astype(float)
        full = aaa.reindex(range(aaa.index.min(), max(aaa.index.max(), years.max()) + 1))
        aaa = np.exp(np.log(full).interpolate(limit_area="inside")).reindex(years)
        if aaa.isna().any():
            raise ValueError("AAA driving costs do not cover the model years")
        out = out.mul(n * aaa / out.sum(axis=1), axis=0)
    return out


def childcare(cfg: dict, years: pd.Index) -> pd.Series:
    c, ay = cfg["childcare"], cfg["model"]["anchor_year"]
    per_year = (c["infant_anchor"] + c["preschool_anchor"]) * c["intensity"]
    return _carry(per_year, "CHILDCARE", years, ay).rename("childcare")


def food(cfg: dict, years: pd.Index) -> pd.DataFrame:
    f, ay = cfg["food"], cfg["model"]["anchor_year"]
    return pd.DataFrame({
        "groceries": _carry(anchor_value(f["groceries_anchor"], ay), "FOOD_HOME", years, ay),
        "restaurants": _carry(anchor_value(f["restaurants_anchor"], ay), "FOOD_AWAY", years, ay),
    })


def household_goods(cfg: dict, years: pd.Index) -> pd.DataFrame:
    g, ay = cfg["household_goods"], cfg["model"]["anchor_year"]
    appliances = sum(
        _carry(item["price"] / item["life"], item["index"], years, ay)
        for item in g["items"].values())
    return pd.DataFrame({
        "appliances": appliances,
        "furnishings": _carry(anchor_value(g["furnishings_anchor"], ay), g["furnishings_index"], years, ay),
    })


def technology(cfg: dict, years: pd.Index) -> pd.DataFrame:
    t, ay = cfg["technology"], cfg["model"]["anchor_year"]
    phones = t["smartphones"] * (t["smartphone_price"] / t["smartphone_life_years"]
                                 + 12 * t["wireless_per_line_month"])
    comms = phones + 12 * t["internet_month"]
    return pd.DataFrame({
        "communications": _carry(comms, t.get("communications_index", "CE_PHONE"), years, ay),
        "tv_and_cable": _carry(12 * t["cable_month"], "CABLE", years, ay),
    })


def healthcare(cfg: dict, years: pd.Index) -> pd.DataFrame:
    h, ay = cfg["healthcare"], cfg["model"]["anchor_year"]
    kff = data.reference("kff_premiums").set_index("year").astype(float)
    kff = kff.reindex(range(kff.index.min(), kff.index.max() + 1)).interpolate()
    # Before KFF's first survey (1999): what married couples with children
    # paid for health insurance (BLS CE, 1988+), then medical services CPI.
    chain = [data._raw_series("ce:HLTHINSR"), data.price_index("MEDICAL_SERVICES", ay)]
    worker = data.splice([kff["worker_family"], *chain])
    total = data.splice([kff["total_family"], *chain])
    return pd.DataFrame({
        "health_premium": worker.reindex(years),
        "health_out_of_pocket": _carry(anchor_value(h["out_of_pocket_anchor"], ay), "MEDICAL", years, ay),
        "health_total_premium": total.reindex(years),
    })


def vacations(cfg: dict, years: pd.Index) -> pd.DataFrame:
    v, ay = cfg["vacations"], cfg["model"]["anchor_year"]
    n = v["travelers"]

    def trip(prefix: str) -> pd.Series:
        return (_carry(n * v[f"{prefix}_airfare_per_person"], "AIRFARE", years, ay)
                + _carry(v[f"{prefix}_nights"] * v[f"{prefix}_lodging_per_night"], "HOTELS", years, ay)
                + _carry((v[f"{prefix}_nights"] + 1) * v[f"{prefix}_daily_food_activities"], "FOOD_AWAY", years, ay))

    return pd.DataFrame({
        "vacation_domestic": v["domestic_trips_per_year"] * trip("domestic"),
        "vacation_international": trip("international") / v["international_every_years"],
    })


def other(cfg: dict, years: pd.Index) -> pd.DataFrame:
    o, ay = cfg["other"], cfg["model"]["anchor_year"]
    items = ["apparel", "personal_care", "household_supplies", "entertainment", "miscellaneous"]
    return pd.DataFrame({k: _carry(anchor_value(o[f"{k}_anchor"], ay), o[f"{k}_index"], years, ay)
                         for k in items})


def build(cfg: dict) -> pd.DataFrame:
    """All working-family line items (nominal dollars) plus helper columns."""
    m = cfg["model"]
    years = pd.Index(range(m["start_year"], m["end_year"] + 1), name="year")
    parts = [
        housing(cfg, years),
        transportation(cfg, years),
        childcare(cfg, years),
        food(cfg, years),
        household_goods(cfg, years),
        technology(cfg, years),
        healthcare(cfg, years),
        vacations(cfg, years),
        other(cfg, years),
    ]
    df = pd.concat(parts, axis=1)
    missing = df[list(CATEGORY)].isna().any()
    if missing.any():
        raise ValueError(f"missing data for: {list(missing[missing].index)}")
    return df


def by_category(df: pd.DataFrame, items: list[str] | None = None) -> pd.DataFrame:
    items = items or list(CATEGORY)
    out = df[items].T.groupby(lambda c: CATEGORY[c]).sum().T
    return out
