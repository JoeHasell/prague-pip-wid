"""
24_fig_top_of_distribution_from_etl.py — the two Q3 figures, from OWID's ETL.

Replaces 15_fig_top_thresholds.py and 16_fig_top1_treemap.py. Those built the
derived series locally from the harmonised file; the ETL now publishes them (see
etl_source.py). This script only reshapes ETL output into the two JSONs the
components already read:

    data/figures/fig_top_thresholds.json   <- fig-top-thresholds
    data/figures/fig_top1_treemap.json     <- fig-top1-treemap

The JSON contracts are unchanged, so no component or slide needs editing.

METHOD (unchanged from the scripts this replaces)
-------------------------------------------------
Every country's 109 bins are pooled into one global distribution, sorted by bin
average income descending, and population is accumulated until the top share is
reached. The threshold reported is the average income of the MARGINAL bin — the
first bin at which the cumulative population reaches the target. For the treemap,
every bin above that point is listed, with the marginal bin clipped to the exact
remaining population and flagged `partial`.

Populations are basis-matched, per the project convention: a per-adult series is
weighted by adult populations, everything else by total populations, and both come
from WID's demography so the two sources' population disagreements never enter.
The ETL publishes exactly that number per country and series, as the
`population_weight` column of inequality_decomposition_by_country.

Run:  python data/scripts/24_fig_top_of_distribution_from_etl.py
"""

import json
from pathlib import Path

import pandas as pd

import etl_source as es

DATA_DIR = Path(__file__).resolve().parents[1]
FIGURES_DIR = DATA_DIR / "figures"

TOP_SHARES = [0.10, 0.01, 0.001]
TREEMAP_SHARE = 0.01

# The seven displayed scenarios, in bridging order, with the population basis
# each one is weighted by. WID post-tax per adult is deliberately not shown.
SCENARIOS = [
    ("WID_pretax_per_adult", "adult"),
    ("WID_pretax_per_capita", "total"),
    ("WID_posttax_per_capita", "total"),
    ("WID_posttax_rescaled", "total"),
    ("PIP_topadj", "total"),
    ("PIP_consinc", "total"),
    ("PIP", "total"),
]

# Region colours, kept as the figure already has them.
REGIONS = [
    ("North America", "#9467bd"),
    ("Western Europe", "#7f7f7f"),
    ("East Asia and Pacific", "#1f77b4"),
    ("Latin America and Caribbean", "#2ca02c"),
    ("Middle East, North Africa, Afghanistan and Pakistan", "#d62728"),
    ("Eastern Europe and Central Asia", "#ff7f0e"),
    ("South Asia", "#8c564b"),
    ("Sub-Saharan Africa", "#e377c2"),
]


def main():
    year = es.DISPLAY_YEAR
    print(f"Reading the ETL cache (display year {year})")
    bins = es.load("display_year_bins")
    by_country = es.load("inequality_decomposition_by_country")

    bins = bins[bins["year"] == year]
    weights = by_country[by_country["year"] == year]

    countries = sorted(bins["country"].unique())
    print(f"  {len(countries)} countries, {bins['series'].nunique()} series")

    thresholds = []
    treemap_scenarios = {}
    for src, basis in SCENARIOS:
        d = global_distribution(bins, weights, src)
        label = es.DECK_SERIES_LABELS[src]

        row = {"source": src, "label": label, "basis": basis}
        for share in TOP_SHARES:
            key = "top" + (f"{share * 100:g}".replace(".", "_"))
            row[key] = round(entry_income(d, share) * es.DAILY_TO_MONTHLY, 2)
        thresholds.append(row)

        top = top_bins(d, TREEMAP_SHARE)
        treemap_scenarios[src] = {"label": label, "basis": basis, "top": top, "global_pop": int(round(d["w"].sum()))}
        print(
            f"  {src:<26} entry ${row['top1']:>10,.0f}/month  "
            f"{len(top):>4d} bins, {top['country'].nunique():>3d} countries"
        )

    write(thresholds_figure(thresholds, countries, year), "fig_top_thresholds.json")
    write(treemap_figure(treemap_scenarios, countries, year), "fig_top1_treemap.json")


def global_distribution(bins, weights, series):
    """Every country's bins for one series, with basis-matched populations attached."""
    d = bins[bins["series"] == series][["country", "percentile", "p_low", "p_high", "avg"]].copy()
    counts = d.groupby("country", observed=True).size()
    assert (counts == 109).all(), f"{series}: countries without 109 bins"

    ref = weights[weights["series"] == series].set_index("country")["population_weight"]
    missing = sorted(set(d["country"]) - set(ref.index))
    assert not missing, f"{series}: no population weight for {missing[:5]}"

    d["w"] = d["country"].map(ref).astype(float) * (d["p_high"] - d["p_low"])
    d = d.rename(columns={"avg": "income"})
    return d[["country", "percentile", "income", "w"]]


def entry_income(d, share):
    """Average income of the marginal bin for the global top `share`."""
    d = d.sort_values("income", ascending=False)
    target = d["w"].sum() * share
    cum = d["w"].cumsum()
    return float(d.loc[cum >= target - 1e-9, "income"].iloc[0])


def top_bins(d, share):
    """Bins inside the global top `share`, with the marginal bin clipped.

    The clipped bin carries only the population still needed to reach the target,
    so the listed populations sum to exactly `share` of the global total."""
    d = d.sort_values("income", ascending=False).reset_index(drop=True)
    target = d["w"].sum() * share
    cum = d["w"].cumsum()
    full = d[cum <= target + 1e-9].copy()
    full["partial"] = False
    remainder = target - full["w"].sum()
    if remainder > 1e-9 and len(full) < len(d):
        marginal = d.iloc[[len(full)]].copy()
        marginal["w"] = remainder
        marginal["partial"] = True
        full = pd.concat([full, marginal], ignore_index=True)
    assert abs(full["w"].sum() - target) < 1e-6 * target, "clipped population does not hit the target"
    return full


def thresholds_figure(thresholds, countries, year):
    return {
        "meta": {
            "title": "What income puts you in the global top 10% / 1% / 0.1%?",
            "top_shares": TOP_SHARES,
            "n_countries": len(countries),
            "year": year,
            "units": "international-$ per month (converted from daily at 365/12)",
            "notes": [
                "The threshold is the average income of the marginal bin — the first "
                "bin at which cumulative population reaches the target share.",
                "Population concept is basis-matched: adults for the per-adult series, "
                "total population otherwise, both from WID's demography.",
                "Computed by OWID's ETL: garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions.",
            ],
            "generated_by": "24_fig_top_of_distribution_from_etl.py",
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        },
        "thresholds": thresholds,
    }


def treemap_figure(scenarios, countries, year):
    regions = es.load("treemap_regions")
    rmap = dict(zip(regions["country"], regions["region"]))
    missing = sorted(c for c in countries if c not in rmap)
    assert not missing, f"countries missing from the region mapping: {missing}"
    region_names = [r for r, _ in REGIONS]

    out = {}
    for src, sc in scenarios.items():
        top = sc["top"]
        # Compact rows: [countryIdx, regionIdx, binLabel, income, pop, partial].
        # Incomes are written PER MONTH; the ranking itself happens on the daily
        # values, which is scale-invariant.
        rows = [
            [
                countries.index(r.country),
                region_names.index(rmap[r.country]),
                r.percentile,
                float(f"{r.income * es.DAILY_TO_MONTHLY:.4g}"),
                int(round(r.w)),
                int(r.partial),
            ]
            for r in top.itertuples()
        ]
        out[src] = {
            "label": sc["label"],
            "basis": sc["basis"],
            "global_pop": sc["global_pop"],
            "threshold": round(float(top["income"].min()) * es.DAILY_TO_MONTHLY, 2),
            "bins": rows,
        }

    return {
        "meta": {
            "title": "Who is in the global top 1%?",
            "top_share": TREEMAP_SHARE,
            "n_countries": len(countries),
            "year": year,
            "units": "international-$ per month (converted from daily at 365/12)",
            "row_format": ["country_index", "region_index", "bin", "income_per_day", "population", "partial"],
            "notes": [
                "Every country-bin inside the global top 1%, ranked by income. The "
                "marginal bin is clipped to the population still needed and flagged "
                "partial, so the listed populations sum to exactly 1% of the global total.",
                "Population concept is basis-matched: adults for the per-adult series, "
                "total population otherwise, both from WID's demography.",
                "Regions are PIP's own current scheme, with Western Europe split out "
                f"of Europe and Central Asia using {es.WESTERN_EUROPE_DEFINITION} — both "
                "from the ETL, so no hand-maintained mapping is involved.",
                "Computed by OWID's ETL: garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions.",
            ],
            "generated_by": "24_fig_top_of_distribution_from_etl.py",
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        },
        "countries": countries,
        "regions": [{"name": n, "color": c} for n, c in REGIONS],
        "scenarios": out,
    }


def write(obj, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    path.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"  wrote {name} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
