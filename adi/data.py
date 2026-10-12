"""Assemble annual (calendar-year) data series from the cached raw sources.

Price indexes are returned with the anchor year normalised to 1.0 so a
component cost is simply ``anchor_dollars * index[year]``. Where a CPI item
starts late (many BLS item indexes begin in December 1997), it is extended
backwards by splicing on a broader or BEA PCE price index; every splice is
listed in ``PRICE_INDEXES`` so it shows up in the methodology appendix.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

from . import sources

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = ROOT / "data" / "reference"


@dataclass(frozen=True)
class IndexSpec:
    label: str
    chain: tuple[str, ...]  # most specific first; "bls:" or "fred:" prefixed


PRICE_INDEXES: dict[str, IndexSpec] = {
    "CPI_ALL": IndexSpec("CPI-U all items", ("bls:CUUR0000SA0",)),
    "CORE": IndexSpec("CPI-U less food and energy", ("bls:CUUR0000SA0L1E",)),
    "FOOD_HOME": IndexSpec("Food at home", ("bls:CUUR0000SAF11",)),
    "FOOD_AWAY": IndexSpec("Food away from home", ("bls:CUUR0000SEFV",)),
    "UTILITIES": IndexSpec("Fuels and utilities", ("bls:CUUR0000SAH2",)),
    "HOME_INSURANCE": IndexSpec(
        "Tenants' and household insurance, spliced to core CPI before 1998",
        ("bls:CUUR0000SEHD", "bls:CUUR0000SA0L1E")),
    "TV": IndexSpec("Televisions", ("bls:CUUR0000SERA01",)),
    "MAJOR_APPLIANCES": IndexSpec(
        "Major appliances, spliced to BEA PCE household appliances before 1998",
        ("bls:CUUR0000SEHK01", "fred:DHAPRG3A086NBEA")),
    "OTHER_APPLIANCES": IndexSpec(
        "Other appliances, spliced to BEA PCE household appliances before 1998",
        ("bls:CUUR0000SEHK02", "fred:DHAPRG3A086NBEA")),
    "LAUNDRY": IndexSpec("Laundry equipment", ("bls:CUUR0000SS30021",)),
    "FURNITURE": IndexSpec("Furniture and bedding", ("bls:CUUR0000SEHJ",)),
    "NEW_VEHICLES": IndexSpec("New vehicles", ("bls:CUUR0000SETA01",)),
    "GASOLINE": IndexSpec("Gasoline (all types)", ("bls:CUUR0000SETB01",)),
    "AUTO_INSURANCE": IndexSpec("Motor vehicle insurance", ("bls:CUUR0000SETE",)),
    "AUTO_MAINTENANCE": IndexSpec("Motor vehicle maintenance and repair", ("bls:CUUR0000SETD",)),
    "AUTO_FEES": IndexSpec(
        "Motor vehicle fees, spliced to CPI-U before 1998",
        ("bls:CUUR0000SETF", "bls:CUUR0000SA0")),
    # Before 1991 the only CPI including childcare is dominated by college
    # tuition (x2.7 in 1980-91 vs x1.5 for wages); childcare is labor-
    # intensive, so it is carried back on average hourly earnings instead.
    "CHILDCARE": IndexSpec(
        "Day care and preschool, spliced to average hourly earnings (production & nonsupervisory) before 1991",
        ("bls:CUUR0000SEEB03", "fred:AHETPI")),
    "WIRELESS": IndexSpec(
        "Wireless telephone services, spliced to BEA PCE telecommunication services before 1998",
        ("bls:CUUR0000SEED03", "fred:DTCSRG3A086NBEA")),
    "PHONE_HARDWARE": IndexSpec(
        "Telephone hardware, spliced to BEA PCE telephone equipment before 1998",
        ("bls:CUUR0000SEEE04", "fred:DTCERG3A086NBEA")),
    "INTERNET": IndexSpec(
        "Internet services, spliced to BEA PCE internet access (1987-97) and telecom services",
        ("bls:CUUR0000SEEE03", "fred:DINTRG3A086NBEA", "fred:DTCSRG3A086NBEA")),
    "CABLE": IndexSpec(
        "Cable, satellite and streaming TV, spliced to BEA PCE telecom services before 1984",
        ("bls:CUUR0000SERA02", "fred:DTCSRG3A086NBEA")),
    "MEDICAL": IndexSpec("Medical care", ("bls:CUUR0000SAM",)),
    "MEDICAL_SERVICES": IndexSpec("Medical care services", ("bls:CUUR0000SAM2",)),
    "AIRFARE": IndexSpec("Airline fares", ("bls:CUUR0000SETG01",)),
    "HOTELS": IndexSpec("Other lodging away from home incl. hotels", ("bls:CUUR0000SEHB02",)),
    "APPAREL": IndexSpec("Apparel", ("bls:CUUR0000SAA",)),
    "PERSONAL_CARE": IndexSpec("Personal care", ("bls:CUUR0000SAG1",)),
    "HOUSEHOLD_SUPPLIES": IndexSpec("Housekeeping supplies", ("bls:CUUR0000SEHN",)),
    # Durable/tech categories whose product changed beyond recognition since
    # 1980 follow what married couples with children actually spent (BLS CE,
    # 1988+, 3-year centered mean), not a quality-adjusted price index.
    "CE_PHONE": IndexSpec(
        "CE telephone services spending, married couples w/ children; CPI-U before 1988",
        ("ce:PHONE", "bls:CUUR0000SA0")),
    "CE_TVAUDIO": IndexSpec(
        "CE audio/visual equipment & services spending, married couples w/ children; CPI-U before 1988",
        ("ce:TVAUDIO", "bls:CUUR0000SA0")),
    "CE_MAJOR_APPLIANCES": IndexSpec(
        "CE major appliance spending, married couples w/ children; CPI-U before 1988",
        ("ce:MAJAPPL", "bls:CUUR0000SA0")),
    "CE_SMALL_APPLIANCES": IndexSpec(
        "CE small appliances & housewares spending, married couples w/ children; CPI-U before 1988",
        ("ce:SMAPPHWR", "bls:CUUR0000SA0")),
    "CE_FURNITURE": IndexSpec(
        "CE furniture spending, married couples w/ children; CPI-U before 1988",
        ("ce:FURNITUR", "bls:CUUR0000SA0")),
    "CE_APPAREL": IndexSpec(
        "CE apparel & services spending, married couples w/ children; CPI-U before 1988",
        ("ce:APPAREL", "bls:CUUR0000SA0")),
    "CE_PERSONAL_CARE": IndexSpec(
        "CE personal care spending, married couples w/ children; CPI-U before 1988",
        ("ce:PERSCARE", "bls:CUUR0000SA0")),
    "CE_HOUSEKEEPING": IndexSpec(
        "CE housekeeping supplies spending, married couples w/ children; CPI-U before 1988",
        ("ce:HKPGSUPP", "bls:CUUR0000SA0")),
    "CE_ENTERTAINMENT": IndexSpec(
        "CE entertainment spending, married couples w/ children; CPI-U before 1988",
        ("ce:ENTRTAIN", "bls:CUUR0000SA0")),
    "CE_MISC": IndexSpec(
        "CE miscellaneous spending, married couples w/ children; CPI-U before 1988",
        ("ce:MISC", "bls:CUUR0000SA0")),
    "ENTERTAINMENT": IndexSpec(
        "Recreation, spliced to core CPI before 1993",
        ("bls:CUUR0000SAR", "bls:CUUR0000SA0L1E")),
}

FRED_SERIES = {
    "hpi": "USSTHPI",             # FHFA all-transactions house price index (1975+)
    "median_new_home": "MSPUS",   # Median sales price of houses sold
    "mortgage_rate": "MORTGAGE30US",
    "auto_loan_rate": "TERMCBAUTO48NS",
    "ft_weekly_earnings": "LEU0252881500A",
}

STATES = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
          "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
          "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
          "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]


def _all_bls_ids() -> list[str]:
    ids = {c[4:] for spec in PRICE_INDEXES.values() for c in spec.chain if c.startswith("bls:")}
    return sorted(ids)


CE_ITEMS = ["PHONE", "TVAUDIO", "MAJAPPL", "SMAPPHWR", "FURNITUR", "APPAREL", "PERSCARE",
            "HKPGSUPP", "ENTRTAIN", "UTILS", "FOODHOME", "FOODAWAY", "MISC", "HEALTH",
            "HLTHINSR", "TOTALEXP"]


def ce(item: str) -> pd.Series:
    """Raw CE annual mean for married couples with children."""
    return sources.ce_annual(item)


# Series used only by the sensitivity analysis (adi/disconnect.py).
EXTRA_FRED = ["GS10", "EXPINF10YR"]


def fetch_all(refresh: bool = False) -> None:
    """Download every raw input the model needs."""
    sources.fetch_bls_cpi(_all_bls_ids(), refresh=refresh)
    sources.fetch_bls_ce(CE_ITEMS, refresh=refresh)
    fred_ids = {c[5:] for spec in PRICE_INDEXES.values() for c in spec.chain if c.startswith("fred:")}
    fred_ids |= set(FRED_SERIES.values())
    fred_ids |= {f"{st}POP" for st in STATES}
    fred_ids |= set(EXTRA_FRED)
    for sid in sorted(fred_ids):
        sources.fetch_fred(sid, refresh=refresh)
    for table in sources.CENSUS_TABLES:
        sources.fetch_census(table, refresh=refresh)
    for table in sources.CENSUS_FAMILY_TABLES:
        sources.fetch_census_families(table, refresh=refresh)


def _raw_series(code: str) -> pd.Series:
    kind, sid = code.split(":", 1)
    if kind == "bls":
        return sources.bls_annual(sid)
    if kind == "ce":
        return _smooth(sources.ce_annual(sid))
    return sources.fred_annual(sid)


def splice(chain: list[pd.Series]) -> pd.Series:
    """Extend ``chain[0]`` backwards and forwards using later fallbacks' growth."""
    out = chain[0].dropna().copy()
    for fallback in chain[1:]:
        fallback = fallback.dropna()
        first, last = out.index.min(), out.index.max()
        parts = [out]
        if fallback.index.min() < first:
            if first not in fallback.index:
                raise ValueError(f"cannot splice: fallback has no value for {first}")
            parts.append(fallback[fallback.index < first] * (out[first] / fallback[first]))
        if fallback.index.max() > last and last in fallback.index:
            parts.append(fallback[fallback.index > last] * (out[last] / fallback[last]))
        out = pd.concat(parts).sort_index()
    return out


def _smooth(s: pd.Series) -> pd.Series:
    """Centered 3-year mean; survey categories are noisy year to year."""
    return s.rolling(3, center=True, min_periods=2).mean()


@lru_cache(maxsize=None)
def price_index(name: str, anchor_year: int) -> pd.Series:
    spec = PRICE_INDEXES[name]
    s = splice([_raw_series(c) for c in spec.chain])
    return s / s[anchor_year]


@lru_cache(maxsize=None)
def fred(name: str) -> pd.Series:
    return sources.fred_annual(FRED_SERIES.get(name, name))


# ---------------------------------------------------------------- income

def _census_median(table: str, *sections: str) -> pd.Series:
    """Median income in current dollars from a Census historical income table.

    ``sections`` is the path of row headings to the block wanted, e.g.
    ("Married-Couple Families", "One or More Children Under 18 Years Old").
    Years with two rows (2013, 2017 methodology breaks) keep the first row
    listed, which is the estimate on the newer, consistent methodology.
    """
    x = pd.read_excel(sources.fetch_census(table), header=None)
    labels = x[0].fillna("").astype(str).str.strip().str.lstrip(".")
    pos = 0
    for section in sections:
        hits = [i for i in labels[labels.str.startswith(section)].index if i >= pos]
        if not hits:
            raise KeyError(f"section {section!r} not found in {table}")
        pos = hits[0] + 1
    rows = {}
    for i in range(pos, len(x)):
        lab = labels[i]
        year = lab[:4]
        if not year.isdigit():
            if rows and x.iloc[i, 1:].isna().all():
                break  # next section heading
            continue
        year = int(year)
        if year not in rows:
            rows[year] = float(x.iloc[i, 2])
    return pd.Series(rows, name=sections[-1]).sort_index()


@lru_cache(maxsize=None)
def incomes() -> pd.DataFrame:
    df = pd.DataFrame({
        "median_household": _census_median("h05", "All Races"),
        "median_married_couple": _census_median("f07ar", "Married-Couple Families"),
        # Alternative benchmarks, used in adi/disconnect.py.
        "median_married_with_children": _census_median(
            "f10ar", "Married-Couple Families", "One or More Children Under 18 Years Old"),
        "median_family_one_earner": _census_median("f12ar", "One Earner"),
        "median_family_two_earners": _census_median("f12ar", "Two Earners"),
        "median_family_head_25_34": _census_median("f11ar", "25 to 34 Years"),
        "median_family_head_35_44": _census_median("f11ar", "35 to 44 Years"),
    })
    df["median_ft_earnings"] = fred("ft_weekly_earnings") * 52
    df.index.name = "year"
    return df


def household_mix() -> pd.DataFrame:
    """Households (thousands) and the share that are married couples, and
    married couples with own children under 18 (Census HH-1 and FM-1)."""
    def table(name: str, cols: dict[int, str]) -> pd.DataFrame:
        x = pd.read_excel(sources.fetch_census_families(name), header=None)
        rows = {}
        for _, r in x.iterrows():
            lab = str(r[0]).strip()
            if lab[:4].isdigit() and int(lab[:4]) not in rows:
                rows[int(lab[:4])] = {v: float(r[k]) for k, v in cols.items()}
        return pd.DataFrame.from_dict(rows, orient="index").sort_index()

    hh = table("hh1", {1: "households", 3: "married_couples"})
    fm = table("fm1", {3: "married_with_children"})
    df = hh.join(fm)
    df["share_married"] = df["married_couples"] / df["households"]
    df["share_married_with_children"] = df["married_with_children"] / df["households"]
    df.index.name = "year"
    return df


# ------------------------------------------------------------- reference

def reference(name: str) -> pd.DataFrame:
    """Hand-collected reference tables in data/reference (see their headers)."""
    return pd.read_csv(REFERENCE / f"{name}.csv", comment="#")


def state_weights(year: int) -> pd.Series:
    pops = {st: sources.fred_annual(f"{st}POP") for st in STATES}
    w = pd.Series({st: s.get(year, s.iloc[-1]) for st, s in pops.items()})
    return w / w.sum()
