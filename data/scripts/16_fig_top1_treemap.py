"""
16_fig_top1_treemap.py — data for the deck figure "fig-top1-treemap".

THE FIGURE (rendered by components/fig-top1-treemap.js)
--------------------------------------------------------
Q3: who are the richest 1%? A treemap of the country-quantile bins that make
up the GLOBAL top 1%, for each of the seven scenarios of the Q2 bridging
charts (chosen with a dropdown). Box area = the bin's population inside the
top 1%; colour = world region; countries are demarcated by heavier borders
(no nested container boxes — every area in the plot IS data).

METHOD (same as the old project's draft treemaps, re-potted)
------------------------------------------------------------
For each scenario, pool every country-bin of the 211-country common sample,
sort by bin average income (descending) and accumulate population. Bins are
included while cumulative population <= 1% of the global population; the
MARGINAL bin (the one that crosses the line) is included with its population
CLIPPED to the remainder, so the total area is exactly 1% of the global
population. The marginal bin is flagged partial in the JSON.

POPULATION CONCEPT (basis-matched, per the project convention — mld.py):
per-adult series: the top 1% OF THE WORLD'S ADULTS (areas = WID adult
populations); per-capita series (incl. PIP and derived): the top 1% of ALL
people (areas = WID total populations).

REGIONS: data/raw/regions/country_region_mapping.csv — World Bank regions,
modified (in the old project, create_modified_region_mapping.py) to split
Europe & Central Asia into Western Europe / Eastern Europe and Central Asia,
and with Afghanistan and Pakistan grouped with Middle East & North Africa.

INPUT   data/processed/pip_wid_harmonized_2023.csv
        data/raw/regions/country_region_mapping.csv
OUTPUT  data/figures/fig_top1_treemap.json

Run:  python data/scripts/16_fig_top1_treemap.py
"""

import json
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, DAILY_TO_MONTHLY, PPP_YEAR
from mld import reference_populations
from scenarios import DISPLAY_SCENARIOS, common_sample, append_derived

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_top1_treemap.json"
REGION_FILE = DATA_DIR / "raw" / "regions" / "country_region_mapping.csv"

TOP_SHARE = 0.01

# Region display order (roughly by expected share of the global top 1%) and
# colours — kept close to the old project's draft palette.
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


def top_bins(d, share):
    """Bins in the global top `share`, marginal bin clipped.

    d needs columns country, percentile, income, w. Returns a DataFrame with
    an added `partial` bool column; sum of w == share * total exactly."""
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
    assert abs(full["w"].sum() - target) < 1e-6 * target
    return full


# Superseded by the ETL pipeline — see legacy_guard.py.
from legacy_guard import require_ack


def main():
    require_ack(
        script='16_fig_top1_treemap.py',
        figures=['fig_top1_treemap.json'],
        replaced_by='24_fig_top_of_distribution_from_etl.py',
    )
    h = pd.read_csv(HARMONIZED_FILE)
    countries = common_sample(h)
    h, rep = append_derived(h, countries)
    regions = pd.read_csv(REGION_FILE)
    rmap = dict(zip(regions["country"], regions["region"]))
    missing = [c for c in countries if c not in rmap]
    assert not missing, f"countries missing from region mapping: {missing}"

    region_names = [r for r, _ in REGIONS]
    scenarios_out = {}
    for sc in DISPLAY_SCENARIOS:
        src, basis = sc["source"], sc["basis"]
        ref_pop = reference_populations(h, "wid", basis)
        d = h[(h.source == src) & (h.country.isin(countries))].copy()
        assert d.groupby("country").size().eq(109).all(), f"missing bins for {src}"
        d["w"] = d["country"].map(ref_pop) * (d["p_high"] - d["p_low"])
        d = d.rename(columns={"average": "income"})

        top = top_bins(d[["country", "percentile", "income", "w"]], TOP_SHARE)
        # Compact rows: [countryIdx, regionIdx, binLabel, income, pop, partial]
        # Incomes are written PER MONTH (config.DAILY_TO_MONTHLY); the ranking
        # itself happens on the daily values (scale-invariant).
        rows = [[countries.index(r.country),
                 region_names.index(rmap[r.country]),
                 r.percentile,
                 float(f"{r.income * DAILY_TO_MONTHLY:.4g}"),
                 int(round(r.w)),
                 int(r.partial)]
                for r in top.itertuples()]
        n_countries = top["country"].nunique()
        scenarios_out[src] = {
            "label": sc["label"], "basis": basis,
            "global_pop": int(round(d["w"].sum())),
            "threshold": round(float(top["income"].min()) * DAILY_TO_MONTHLY, 2),
            "bins": rows,
        }
        print(f"{src:26s} {len(rows):4d} bins, {n_countries:3d} countries, "
              f"entry ${top['income'].min() * DAILY_TO_MONTHLY:,.0f}/month, "
              f"pop {top['w'].sum() / 1e6:.1f}M ({basis}s)"
              .replace("(totals)", "(people)"))

    out = {
        "meta": {
            "title": "Who is in the global top 1%?",
            "top_share": TOP_SHARE,
            "n_countries": len(countries),
            "year": 2023,
            "units": f"international-$ PER MONTH (PIP: 2021 PPPs; WID: {PPP_YEAR} "
                     "PPPs); converted from daily values at 365/12",
            "row_format": ["country_index", "region_index", "bin",
                           "income_per_day", "population", "partial"],
            "notes": [
                "Bins sorted by average income; population accumulated to 1% "
                "of the global population; the marginal bin is included with "
                "its population clipped (partial=1).",
                "Population concept is basis-matched (mld.py convention): "
                "per-adult series rank the world's ADULTS; per-capita series "
                "rank all people. Weights are WID demography throughout.",
                "Regions: World Bank classification, modified — Western "
                "Europe split from Europe & Central Asia; Afghanistan and "
                "Pakistan grouped with Middle East & North Africa "
                "(data/raw/regions/country_region_mapping.csv).",
            ],
            "generated_by": "data/scripts/16_fig_top1_treemap.py",
        },
        "countries": countries,
        "regions": [{"name": r, "color": c} for r, c in REGIONS],
        "scenarios": scenarios_out,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nSaved: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
