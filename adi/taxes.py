"""Gross-up after-tax spending to the pre-tax income a family must earn.

Taxes come from NBER TAXSIM 35: federal income tax, state income tax, and
the employee share of FICA, for a married couple filing jointly with two
young children who deduct mortgage interest and property tax (when
itemizing beats the standard deduction) and claim the child and dependent
care credit on their childcare spending.

State tax is a population-weighted average over all 50 states + DC, using
each year's state populations (Census, via FRED).

For each year and scenario the household is run at a grid of gross incomes,
and the gross income whose after-tax amount equals the required spending is
found by interpolation. TAXSIM 35 models tax law through 2023; later years
apply 2023 law to CPI-deflated amounts (brackets, deductions and the FICA
wage base are inflation indexed, so this is a close approximation).
"""

from __future__ import annotations

import gzip
import hashlib
import io

import numpy as np
import pandas as pd

from . import data, sources

# Gross incomes run at, as multiples of the year's median married-couple
# income. Keeping the grid independent of modeled spending lets the TAXSIM
# cache survive assumption changes that don't touch deductions.
GRID = np.round(np.linspace(0.5, 3.5, 16), 4)
CACHE_DIR = sources.RAW / "taxsim"


def _cached_taxsim(inputs: pd.DataFrame) -> pd.DataFrame:
    key = hashlib.sha256(inputs.to_csv(index=False).encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{key}.csv.gz"
    if path.exists():
        return pd.read_csv(path)
    out = sources.taxsim(inputs)[["taxsimid", "fiitax", "siitax", "tfica"]]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as fh:
        out.to_csv(fh, index=False)
    return out


def tax_grid(households: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Taxes on a grid of gross incomes for each (year, scenario) household.

    ``households`` has one row per (year, scenario) with columns ``base``
    (median married-couple income), ``earners`` (1 or 2),
    ``mortgage_interest``, ``property_tax`` and ``childcare``.
    Returns a long frame: year, scenario, gross, federal, state, fica, total.
    """
    t, hh = cfg["taxes"], cfg["household"]
    last = t["last_taxsim_year"]
    cpi = data.price_index("CPI_ALL", last)
    states = list(range(1, len(data.STATES) + 1)) if t["include_state"] else [0]

    rows = []
    for (year, scen), h in households.iterrows():
        deflate = 1.0 if year <= last else float(cpi[year])
        for mult in GRID:
            gross = round(h["base"] * mult, 0)
            split = hh["primary_earner_share"] if h["earners"] == 2 else 1.0
            rows.append({
                "year": year, "scenario": scen, "gross": gross, "deflate": deflate,
                "tax_year": min(year, last), "mstat": 2,
                "page": hh["parent_age"], "sage": hh["parent_age"],
                "depx": hh["children"], "age1": hh["child_ages"][0], "age2": hh["child_ages"][1],
                "pwages": round(gross * split / deflate, 2),
                "swages": round(gross * (1 - split) / deflate, 2),
                "mortgage": round(h["mortgage_interest"] / deflate, 2),
                "proptax": round(h["property_tax"] / deflate, 2),
                "childcare": round(h["childcare"] / deflate, 2),
            })
    base = pd.DataFrame(rows)
    full = base.loc[base.index.repeat(len(states))].reset_index(drop=True)
    full["state"] = np.tile(states, len(base))
    full["taxsimid"] = np.arange(1, len(full) + 1)
    cols = ["taxsimid", "tax_year", "state", "mstat", "page", "sage", "depx", "age1", "age2",
            "pwages", "swages", "mortgage", "proptax", "childcare"]
    inputs = full[cols].rename(columns={"tax_year": "year"})
    res = full.merge(_cached_taxsim(inputs), on="taxsimid")
    for c in ["fiitax", "siitax", "tfica"]:
        res[c] = res[c] * res["deflate"]

    if t["include_state"]:
        weights = {y: data.state_weights(y) for y in res["year"].unique()}
        res["w"] = [weights[y].iloc[s - 1] for y, s in zip(res["year"], res["state"])]
    else:
        res["w"] = 1.0
    res["state_tax"] = res["siitax"] * res["w"]
    res["fed_w"] = res["fiitax"] * res["w"]
    res["fica_w"] = res["tfica"] * res["w"]
    g = res.groupby(["year", "scenario", "gross"], as_index=False)[["fed_w", "state_tax", "fica_w"]].sum()
    g = g.rename(columns={"fed_w": "federal", "state_tax": "state", "fica_w": "fica"})
    g["total"] = g["federal"] + g["state"] + g["fica"]
    return g


def required_gross(households: pd.DataFrame, grid: pd.DataFrame) -> pd.DataFrame:
    """Gross income at which income minus taxes equals the spending need."""
    out = []
    for (year, scen), h in households.iterrows():
        g = grid[(grid["year"] == year) & (grid["scenario"] == scen)].sort_values("gross")
        net = g["gross"] - g["total"]
        if not (net.diff().dropna() > 0).all():
            raise ValueError(f"after-tax income not increasing in gross for {year} {scen}")
        need = h["spending"]
        if need < net.iloc[0] or need > net.iloc[-1]:
            raise ValueError(f"spending {need:,.0f} outside tax grid for {year} {scen}")
        gross = float(np.interp(need, net, g["gross"]))
        parts = {c: float(np.interp(gross, g["gross"], g[c])) for c in ["federal", "state", "fica"]}
        out.append({"year": year, "scenario": scen, "gross_required": gross, **parts})
    return pd.DataFrame(out).set_index(["year", "scenario"])
