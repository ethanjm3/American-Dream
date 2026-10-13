"""Command line: ``python -m adi [fetch|build|charts|web|disconnect|budget|all]``."""

from __future__ import annotations

import argparse

from . import charts, data, disconnect, index, web


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="adi", description="American Dream Index")
    p.add_argument("command", nargs="?", default="all",
                   choices=["fetch", "build", "charts", "web", "disconnect", "budget", "all"])
    p.add_argument("--config", default=index.DEFAULT_CONFIG)
    p.add_argument("--refresh", action="store_true", help="re-download raw data")
    p.add_argument("--year", type=int, default=None, help="budget: index year (default: latest)")
    p.add_argument("--scenario", choices=list(index.SCENARIOS), default="A", help="budget: household")
    p.add_argument("--gross", type=float, default=None,
                   help="budget: gross income (default: median married-couple income)")
    args = p.parse_args(argv)

    if args.command == "budget":
        _budget(args)
        return

    if args.command in ("fetch", "all") or args.refresh:
        data.fetch_all(refresh=args.refresh)
        if args.command == "fetch":
            return
    cfg = index.load_config(args.config)
    if args.command == "disconnect":
        out = disconnect.run(cfg)
        for path in out["_charts"]:
            print(f"wrote {path.relative_to(index.ROOT)}")
        print(out["decomposition"].round(3).to_string(index=False))
        return
    results = index.build(cfg)
    index.save(results)
    if args.command in ("charts", "all"):
        for path in charts.render_all(results):
            print(f"wrote {path.relative_to(index.ROOT)}")
    if args.command in ("web", "all"):
        print(f"wrote {web.export(results, cfg).relative_to(index.ROOT)}")
    s = results["summary"]
    latest, first = s["year"].max(), s["year"].min()
    for scen, label in index.SCENARIOS.items():
        row0 = s[(s.scenario == scen) & (s.year == first)].iloc[0]
        row1 = s[(s.scenario == scen) & (s.year == latest)].iloc[0]
        print(f"{label}: {first} ${row0.cost_pretax:,.0f} "
              f"({row0.pct_of_married_couple_income:.0%} of median married-couple income, "
              f"{row0.earners_needed:.2f} earners) -> {latest} ${row1.cost_pretax:,.0f} "
              f"({row1.pct_of_married_couple_income:.0%}, {row1.earners_needed:.2f} earners)")


def _budget(args) -> None:
    from .budget import household

    year = args.year or index.load_config(args.config)["model"]["end_year"]
    out = household.run(year, args.scenario, args.gross)
    cats, months, meta = out["categories"], out["months"], out["meta"]
    funded = 1 - cats["shortfall"].sum() / cats["annual_cost"].sum()
    print(f"{index.SCENARIOS[args.scenario]}, {year}: gross ${meta['gross']:,.0f}, "
          f"take-home ${meta['take_home']:,.0f} (lifestyle needs ${meta['required_gross']:,.0f} gross)")
    print(months.to_string(index=False))
    print(cats[["category", "annual_cost", "spent_or_saved", "shortfall", "funded_share"]]
          .round(0).to_string(index=False))
    print(f"Lifestyle funded: {funded:.0%}")


if __name__ == "__main__":
    main()
