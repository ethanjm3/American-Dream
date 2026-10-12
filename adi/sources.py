"""Download and cache raw data from public sources.

Every fetcher writes its raw response under ``data/raw`` so the model can be
rebuilt offline and every number can be traced back to a file. Re-download
with ``python -m adi fetch``.

Sources
-------
* FRED (St. Louis Fed) -- house prices, mortgage rates, income, BEA PCE prices
* BLS CPI flat files (download.bls.gov/pub/time.series/cu) -- CPI-U components
* Census CPS ASEC historical income tables -- household / family medians
* NBER TAXSIM 35 -- federal + state income tax and FICA
"""

from __future__ import annotations

import io
import os
import time
import uuid
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CACHE = ROOT / ".cache"

# BLS rejects automated requests whose User-Agent lacks a contact email.
# Set ADI_CONTACT_EMAIL to your own address when re-downloading.
CONTACT = os.environ.get("ADI_CONTACT_EMAIL", "adi-research@example.com")
USER_AGENT = f"american-dream-index/1.0 (research; contact: {CONTACT})"

BLS_BASE = "https://download.bls.gov/pub/time.series/cu/"
# CPI flat files that together hold every series the model uses.
BLS_FILES = [
    "cu.data.1.AllItems",
    "cu.data.2.Summaries",
    "cu.data.11.USFoodBeverage",
    "cu.data.12.USHousing",
    "cu.data.13.USApparel",
    "cu.data.14.USTransportation",
    "cu.data.15.USMedical",
    "cu.data.16.USRecreation",
    "cu.data.17.USEducationAndCommunication",
    "cu.data.18.USOtherGoodsAndServices",
    "cu.data.20.USCommoditiesServicesSpecial",
]


def _get(url: str, *, retries: int = 4, **kw) -> requests.Response:
    headers = {"User-Agent": USER_AGENT, **kw.pop("headers", {})}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=120, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


# --------------------------------------------------------------------------- FRED

def fetch_fred(series_id: str, refresh: bool = False) -> Path:
    path = RAW / "fred" / f"{series_id}.csv"
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", params={"id": series_id})
    path.write_bytes(r.content)
    return path


def fred_annual(series_id: str, how: str = "mean") -> pd.Series:
    """Calendar-year aggregate of a FRED series (index = int year)."""
    df = pd.read_csv(fetch_fred(series_id))
    date_col, val_col = df.columns[0], df.columns[1]
    s = pd.to_numeric(df[val_col], errors="coerce")
    s.index = pd.to_datetime(df[date_col])
    s = s.dropna()
    g = s.groupby(s.index.year)
    out = g.mean() if how == "mean" else g.last()
    # Only keep complete years for sub-annual data (avoid a partial current year).
    counts = g.count()
    freq = counts.median()
    if freq > 1:
        out = out[counts >= freq * 0.99]
    out.name = series_id
    return out


# ---------------------------------------------------------------------- BLS CPI

def fetch_bls_cpi(series_ids: list[str], refresh: bool = False) -> Path:
    """Extract annual averages for ``series_ids`` from the BLS CPI flat files.

    The flat files are large, so they are cached under ``.cache`` (ignored by
    git) and only the extracted annual series are written to ``data/raw``.
    """
    out = RAW / "bls" / "cpi_annual.csv"
    if out.exists() and not refresh:
        have = set(pd.read_csv(out).columns) - {"year"}
        if set(series_ids) <= have:
            return out
    CACHE.mkdir(exist_ok=True)
    wanted = {s.ljust(17) for s in series_ids} | set(series_ids)
    rows = []
    for name in BLS_FILES:
        path = CACHE / name
        if not path.exists() or refresh:
            path.write_bytes(_get(BLS_BASE + name).content)
        df = pd.read_csv(path, sep="\t", dtype=str)
        df.columns = [c.strip() for c in df.columns]
        df = df[df["series_id"].isin(wanted)]
        rows.append(df)
    data = pd.concat(rows)
    data["series_id"] = data["series_id"].str.strip()
    data["year"] = data["year"].astype(int)
    data["value"] = pd.to_numeric(data["value"].str.strip(), errors="coerce")
    # Some series appear in more than one file.
    data = data.drop_duplicates(["series_id", "year", "period"])
    monthly = data[data["period"].str.match(r"M(0[1-9]|1[0-2])")]
    annual_reported = data[data["period"] == "M13"].set_index(["series_id", "year"])["value"]
    # Annual average: BLS M13 where published, else mean of 12 months.
    g = monthly.groupby(["series_id", "year"])["value"]
    computed = g.mean()[g.count() == 12]
    annual = computed.combine_first(annual_reported)
    annual.update(annual_reported)
    wide = annual.unstack("series_id").sort_index()
    missing = set(series_ids) - set(wide.columns)
    if missing:
        raise KeyError(f"BLS series not found: {sorted(missing)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    wide.index.name = "year"
    wide.to_csv(out)
    return out


def bls_annual(series_id: str) -> pd.Series:
    df = pd.read_csv(RAW / "bls" / "cpi_annual.csv", index_col="year")
    return df[series_id].dropna()


# ----------------------------------------------------------------------- Census

CENSUS_BASE = "https://www2.census.gov/programs-surveys/cps/tables/time-series/"
CENSUS_TABLES = {
    # All-races household income, current and 2024 dollars.
    "h05": "historical-income-households/h05.xlsx",
    # Families by type (married-couple), median income.
    "f07ar": "historical-income-families/f07ar.xlsx",
}


def fetch_census(table: str, refresh: bool = False) -> Path:
    path = RAW / "census" / f"{table}.xlsx"
    if path.exists() and not refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_get(CENSUS_BASE + CENSUS_TABLES[table]).content)
    return path


# ----------------------------------------------------------------------- TAXSIM

TAXSIM_URL = "https://taxsim.nber.org/taxsim35/redirect.cgi"


def taxsim(df: pd.DataFrame, chunk: int = 1500, workers: int = 4) -> pd.DataFrame:
    """Run a batch through the NBER TAXSIM 35 web service.

    ``df`` uses TAXSIM's input column names (taxsimid, year, state, mstat,
    page, sage, depx, age1.., pwages, swages, mortgage, proptax, childcare).
    Returns fiitax, siitax, fica (employee + employer) and tfica (employee).

    The service stops each request after ~60 seconds (about 2,000 records
    with state taxes), so the batch is sent in chunks, a few at a time.
    """
    from concurrent.futures import ThreadPoolExecutor

    chunks = [df.iloc[i:i + chunk] for i in range(0, len(df), chunk)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(_taxsim_once, chunks))
    return pd.concat(parts, ignore_index=True)


def _taxsim_once(df: pd.DataFrame) -> pd.DataFrame:
    # TAXSIM's CGI parses the upload naively and only accepts curl-style
    # multipart boundaries, so the body is built by hand.
    boundary = "-" * 24 + uuid.uuid4().hex[:16]
    body = (f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="txpydata.raw"; filename="txpydata.raw"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
            f"{df.to_csv(index=False)}\r\n--{boundary}--\r\n").encode()
    headers = {"User-Agent": USER_AGENT,
               "Content-Type": f"multipart/form-data; boundary={boundary}"}
    for attempt in range(4):
        try:
            r = requests.post(TAXSIM_URL, data=body, headers=headers, timeout=600)
            r.raise_for_status()
            if not r.text.startswith("taxsimid"):
                raise RuntimeError(f"TAXSIM error: {r.text[:500]}")
            out = pd.read_csv(io.StringIO(r.text), skipinitialspace=True)
            out.columns = [c.strip() for c in out.columns]
            ids = pd.to_numeric(out["taxsimid"], errors="coerce")
            if ids.isna().any() or len(out) != len(df):
                bad = out.loc[ids.isna(), "taxsimid"].head(1).tolist()
                raise RuntimeError(f"TAXSIM returned {len(out)} rows for {len(df)} {bad}")
            out["taxsimid"] = ids.astype(int)
            return out
        except (requests.RequestException, pd.errors.ParserError, RuntimeError):
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    raise AssertionError("unreachable")


# ------------------------------------------------- BLS Consumer Expenditure

CE_URL = "https://download.bls.gov/pub/time.series/cx/cx.data.1.AllData"
# Married couples with children (CE "composition of consumer unit" 04), mean.
CE_GROUP = "LB0604M"


def fetch_bls_ce(items: list[str], refresh: bool = False) -> Path:
    """Annual mean spending per consumer unit for married couples with children."""
    out = RAW / "bls" / "ce_married_with_children.csv"
    if out.exists() and not refresh:
        have = set(pd.read_csv(out).columns) - {"year"}
        if set(items) <= have:
            return out
    CACHE.mkdir(exist_ok=True)
    path = CACHE / "cx.data.1.AllData"
    if not path.exists() or refresh:
        path.write_bytes(_get(CE_URL).content)
    wanted = {f"CXU{item}{CE_GROUP}": item for item in items}
    rows = []
    with open(path) as fh:
        next(fh)
        for line in fh:
            sid = line[:30].strip()
            if sid in wanted:
                _, year, period, value, *_ = (p.strip() for p in line.split("\t"))
                rows.append((wanted[sid], int(year), float(value)))
    df = pd.DataFrame(rows, columns=["item", "year", "value"])
    wide = df.pivot(index="year", columns="item", values="value").sort_index()
    missing = set(items) - set(wide.columns)
    if missing:
        raise KeyError(f"CE items not found: {sorted(missing)}")
    out.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(out)
    return out


def ce_annual(item: str) -> pd.Series:
    df = pd.read_csv(RAW / "bls" / "ce_married_with_children.csv", index_col="year")
    return df[item].dropna()
