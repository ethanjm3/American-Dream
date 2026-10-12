"""Static charts (PNG + SVG) of the American Dream Index."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "charts"

# Validated categorical palette (light surface), fixed slot order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

STACK_ORDER = ["Housing", "Transportation", "Childcare", "Food", "Healthcare",
               "Retirement saving", "Taxes", "Everything else"]
EVERYTHING_ELSE = ["Household goods", "Technology", "Vacations", "Other necessities"]


def _style(ax, title: str, subtitle: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.set_title(title, loc="left", fontsize=13, color=INK, fontweight="semibold", pad=26)
    ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9.5, color=INK_2, va="bottom")


def _legend_below(ax, ncol: int) -> None:
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=ncol, frameon=False,
              fontsize=9, labelcolor=INK_2, handlelength=1.6, columnspacing=1.6)


def _money(x, _=None) -> str:
    return f"${x / 1000:,.0f}K" if abs(x) >= 1000 else f"${x:,.0f}"


def _end_label(ax, x, y, text, dy: float = 0.0) -> None:
    ax.annotate(text, (x, y), xytext=(6, dy), textcoords="offset points",
                va="center", fontsize=9, color=INK_2)


def _source(fig, y: float = -0.06) -> None:
    fig.text(0.01, y, "Sources: FHFA, Freddie Mac, BLS CPI & CE, Census CPS, KFF, AAA, "
             "Child Care Aware, NBER TAXSIM. See docs/methodology.md.",
             fontsize=7.5, color=MUTED)


def _save(fig, name: str) -> list[Path]:
    OUT.mkdir(exist_ok=True)
    paths = []
    for ext in ("png", "svg"):
        p = OUT / f"{name}.{ext}"
        fig.savefig(p, dpi=200, bbox_inches="tight", facecolor=SURFACE)
        paths.append(p)
    plt.close(fig)
    return paths


def _real(df: pd.DataFrame, cpi: pd.Series, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    deflator = cpi.reindex(out["year"]).to_numpy()
    for c in cols:
        out[c] = out[c] / deflator
    return out


def cost_vs_income(summary: pd.DataFrame, cpi: pd.Series, base_year: int) -> list[Path]:
    a = _real(summary[summary.scenario == "A"], cpi,
              ["cost_pretax", "median_married_couple", "median_household"])
    fig, ax = plt.subplots(figsize=(9, 5.2))
    lines = [
        ("cost_pretax", "Cost of the American Dream", SERIES[0]),
        ("median_married_couple", "Median married-couple income", SERIES[1]),
        ("median_household", "Median household income", SERIES[2]),
    ]
    for col, label, color in lines:
        ax.plot(a["year"], a[col], color=color, linewidth=2, solid_capstyle="round", label=label)
        ax.plot(a["year"].iloc[-1], a[col].iloc[-1], "o", color=color, markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=2)
        _end_label(ax, a["year"].iloc[-1], a[col].iloc[-1], _money(a[col].iloc[-1]))
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax.set_ylim(0, None)
    ax.set_xlim(a["year"].min(), a["year"].max() + 4)
    _legend_below(ax, 3)
    first, last = a.iloc[0], a.iloc[-1]
    _style(ax, f"The lifestyle costs {last['cost_pretax'] / last['median_married_couple']:.1f}× the median "
               f"married couple's income ({first['cost_pretax'] / first['median_married_couple']:.1f}× in {int(first['year'])})",
           f"Pre-tax income needed for the lifestyle (two earners, paid childcare) vs. median income, {base_year} dollars")
    _source(fig)
    return _save(fig, "01_cost_vs_income")


def share_of_income(summary: pd.DataFrame) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for i, (scen, label) in enumerate([("A", "Two earners, paid childcare"),
                                       ("B", "One earner, parent at home")]):
        s = summary[summary.scenario == scen]
        ax.plot(s["year"], 100 * s["pct_of_married_couple_income"], color=SERIES[i], linewidth=2, label=label)
        ax.plot(s["year"].iloc[-1], 100 * s["pct_of_married_couple_income"].iloc[-1], "o",
                color=SERIES[i], markersize=6, markeredgecolor=SURFACE, markeredgewidth=2)
        _end_label(ax, s["year"].iloc[-1], 100 * s["pct_of_married_couple_income"].iloc[-1],
                   f"{100 * s['pct_of_married_couple_income'].iloc[-1]:.0f}%")
    ax.axhline(100, color=INK_2, linewidth=1)
    ax.text(summary["year"].min() + 0.3, 101.5, "100% = all of the median married couple's income",
            fontsize=8.5, color=INK_2, va="bottom")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}%"))
    ax.set_ylim(0, None)
    ax.set_xlim(summary["year"].min(), summary["year"].max() + 4)
    _legend_below(ax, 2)
    _style(ax, "Share of median married-couple income the lifestyle requires",
           "Pre-tax cost of the American Dream ÷ Census median married-couple family income")
    _source(fig)
    return _save(fig, "02_share_of_income")


def earners_needed(summary: pd.DataFrame) -> list[Path]:
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for i, (scen, label) in enumerate([("A", "Two earners, paid childcare"),
                                       ("B", "One earner, parent at home")]):
        s = summary[summary.scenario == scen]
        ax.plot(s["year"], s["earners_needed"], color=SERIES[i], linewidth=2, label=label)
        ax.plot(s["year"].iloc[-1], s["earners_needed"].iloc[-1], "o", color=SERIES[i],
                markersize=6, markeredgecolor=SURFACE, markeredgewidth=2)
        _end_label(ax, s["year"].iloc[-1], s["earners_needed"].iloc[-1], f"{s['earners_needed'].iloc[-1]:.1f}")
        first = s.iloc[0]
        ax.annotate(f"{first['earners_needed']:.1f}", (first["year"], first["earners_needed"]),
                    xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9, color=INK_2)
    for level, text in ((1, "1 earner"), (2, "2 earners")):
        ax.axhline(level, color=AXIS, linewidth=1)
        ax.text(summary["year"].max() + 4, level, text, fontsize=8.5, color=MUTED, va="center", ha="right")
    ax.set_ylim(0, None)
    ax.set_xlim(summary["year"].min() - 1, summary["year"].max() + 4)
    _legend_below(ax, 2)
    _style(ax, "Full-time median paychecks needed to fund the American Dream",
           "Pre-tax cost ÷ median annual earnings of a full-time wage and salary worker (BLS)")
    _source(fig)
    return _save(fig, "03_earners_needed")


def breakdown(summary: pd.DataFrame, cpi: pd.Series, base_year: int, scenario: str = "A") -> list[Path]:
    s = summary[summary.scenario == scenario].set_index("year")
    cats = {c[5:]: s[c] for c in s.columns if c.startswith("cat: ")}
    df = pd.DataFrame(cats)
    df["Everything else"] = df[[c for c in EVERYTHING_ELSE if c in df]].sum(axis=1)
    df = df[[c for c in STACK_ORDER if c in df]]
    df = df.div(cpi.reindex(df.index), axis=0)
    years = [y for y in range(df.index.min(), df.index.max() + 1, 5)]
    if df.index.max() not in years:
        years.append(df.index.max())
    df = df.loc[years]

    fig, ax = plt.subplots(figsize=(10, 5.6))
    bottom = pd.Series(0.0, index=df.index)
    width = 2.6
    for i, col in enumerate(df.columns):
        ax.bar(df.index, df[col], width, bottom=bottom, color=SERIES[i], label=col,
               edgecolor=SURFACE, linewidth=1.2)
        bottom += df[col]
    for y, total in bottom.items():
        ax.annotate(_money(total), (y, total), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8.5, color=INK_2)
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax.set_xticks(df.index)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=9,
              labelcolor=INK_2, reverse=True)
    label = "two earners, paid childcare" if scenario == "A" else "one earner, parent at home"
    _style(ax, "Where the money goes",
           f"Pre-tax cost of the lifestyle by category ({label}), {base_year} dollars")
    _source(fig)
    return _save(fig, f"04_breakdown_{scenario}")


def render_all(results: dict[str, pd.DataFrame]) -> list[Path]:
    summary = results["summary"]
    cpi = results["cpi"]["cpi"]
    base_year = int(summary["year"].max())
    paths = []
    paths += cost_vs_income(summary, cpi, base_year)
    paths += share_of_income(summary)
    paths += earners_needed(summary)
    paths += breakdown(summary, cpi, base_year, "A")
    paths += breakdown(summary, cpi, base_year, "B")
    return paths


# ----------------------------------------------------------- disconnect charts

def yardsticks(summary: pd.DataFrame, inc: pd.DataFrame) -> list[Path]:
    """Cost relative to four income yardsticks, indexed to 1980 = 100."""
    a = summary[summary.scenario == "A"].set_index("year")["cost_pretax"]
    lines = [
        ("median_ft_earnings", "One full-time paycheck"),
        ("median_household", "Median household"),
        ("median_married_couple", "Median married couple"),
        ("median_married_with_children", "Median married couple with children"),
    ]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for i, (col, label) in enumerate(lines):
        r = a / inc[col].reindex(a.index)
        r = 100 * r / r.iloc[0]
        ax.plot(r.index, r, color=SERIES[i], linewidth=2, label=label)
        ax.plot(r.index[-1], r.iloc[-1], "o", color=SERIES[i], markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=2)
        _end_label(ax, r.index[-1], r.iloc[-1], f"{r.iloc[-1]:.0f}")
    ax.axhline(100, color=INK_2, linewidth=1)
    ax.set_ylim(55, 110)
    ax.set_xlim(a.index.min(), a.index.max() + 4)
    _legend_below(ax, 2)
    _style(ax, "Whether it got cheaper depends on whose income you measure against",
           "Pre-tax cost of the lifestyle (two earners, paid childcare) ÷ each income, 1980 = 100")
    _source(fig, -0.12)
    return _save(fig, "05_yardsticks")


def paycheck_changes(cat: pd.DataFrame) -> list[Path]:
    """Change in each category's cost, in median full-time paychecks."""
    df = cat.drop(index="Total")[["change_1980_2025", "change_2019_2025"]]
    df = df.sort_values("change_1980_2025")
    fig, ax = plt.subplots(figsize=(9, 5.6))
    y = np.arange(len(df))
    h = 0.36
    ax.barh(y + h / 2, df["change_1980_2025"], h, color=SERIES[0], label="1980 → 2025")
    ax.barh(y - h / 2, df["change_2019_2025"], h, color=SERIES[1], label="2019 → 2025")
    for yi, v in zip(y, df["change_1980_2025"]):
        ax.annotate(f"{v:+.2f}", (v, yi + h / 2), xytext=(4 if v >= 0 else -4, 0), textcoords="offset points",
                    ha="left" if v >= 0 else "right", va="center", fontsize=8.5, color=INK_2)
    ax.set_yticks(y, df.index)
    lo, hi = df.min().min(), df.max().max()
    ax.set_xlim(lo * 1.22, hi * 1.15)
    ax.axvline(0, color=AXIS, linewidth=1)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", labelsize=9.5, labelcolor=INK_2)
    _legend_below(ax, 2)
    tot = cat.loc["Total"]
    _style(ax, "What got dearer and what got cheaper, in paychecks",
           f"Change in each category's cost, in median full-time paychecks (total {tot['change_1980_2025']:+.2f} "
           f"since 1980, {tot['change_2019_2025']:+.2f} since 2019)")
    ax.grid(axis="y", visible=False)
    _source(fig)
    return _save(fig, "06_paycheck_changes")
