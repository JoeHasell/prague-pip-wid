"""
25_fig_scatters_from_etl.py — the Q1 cross-source scatters, from OWID's ETL.

These are the figures whose numbers used to be pasted into the component files as
literal arrays (58 countries in gini-pip-wid-scatter.js, 115 in ineq-trend.js).
They came from OWID originally, but as a one-off extraction: the extraction
scripts were never committed, so there was no way to refresh them. This script
regenerates both from the ETL dataset they came from, so they update with it:

    data/figures/fig_gini_scatter.json   <- gini-pip-wid-scatter
    data/figures/fig_ineq_trend.json     <- ineq-trend-scatter, ineq-change-scatter

WHY THIS READS THE COMPARISON DATASET, NOT THE BIN-LEVEL DISTRIBUTIONS
----------------------------------------------------------------------
`poverty_inequality/2025-01-22/inequality_comparison` already does the hard part:
for each country it picks the observation nearest each reference year (1993 and
2019, at most five years away, excluding 1988-89 and 2020-24), preferring the same
welfare concept and reporting level. Recomputing these measures from the harmonised
109-bin distributions would be a different figure — every country would have a
value for every year, so the ~2019 scatter would jump from 58 points to 211, and
the measures would be bin-based rather than each source's published ones.

Reading the comparison dataset keeps this a refresh rather than a redefinition.
It is also why the top-1% panel is empty for PIP: PIP publishes no top-1% share,
so the dataset has no such column, and the deck's blank PIP panel is correct.

Post-tax WID Gini is the one thing the comparison dataset does not carry (it holds
pre-tax only), so it is joined from the WID dataset at the same country-years.

Run:  python data/scripts/25_fig_scatters_from_etl.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"

# The variant that keeps every country with data, rather than only the countries
# present in every series — this is what the scatters were built from.
VARIANT = "All data points"
REF_YEARS = {"1993": "93", "2019": "19"}
SCATTER_REF_YEAR = "2019"

# comparison-dataset column -> (metric, source) in the figures' own vocabulary
MEASURES = {
    "gini_pip_disposable_percapita": ("gini", "pip"),
    "gini_wid_pretaxnational_peradult": ("gini", "wid"),
    "p90p100share_pip_disposable_percapita": ("top10", "pip"),
    "p90p100share_wid_pretaxnational_peradult": ("top10", "wid"),
    "palmaratio_pip_disposable_percapita": ("palma", "pip"),
    "palmaratio_wid_pretaxnational_peradult": ("palma", "wid"),
    # PIP has no top-1% counterpart; the figure's PIP panel is empty by design.
    "p99p100share_wid_pretaxnational_peradult": ("top1", "wid"),
}


def main():
    print("Reading the ETL cache")
    comp = es.load("inequality_comparison")
    posttax = es.load("wid_posttax_gini")
    regions = es.load("country_regions").set_index("country")["region"]

    # ref_year round-trips through the CSV cache as an integer; the keys here are
    # strings, so normalise before filtering.
    comp["ref_year"] = comp["ref_year"].astype(str)
    comp = comp[comp["only_all_series"] == VARIANT]
    assert not comp.empty, f"no rows for variant {VARIANT!r}"
    assert set(comp["ref_year"]) == set(REF_YEARS), (
        f"unexpected reference years: {sorted(set(comp['ref_year']))}"
    )

    collapsed = collapse(comp)
    write(gini_scatter(collapsed, posttax, regions), "fig_gini_scatter.json")
    write(trend_scatter(collapsed, regions), "fig_ineq_trend.json")


def collapse(comp):
    """One row per (country, ref_year) per measure, with the year it came from.

    Each measure's value sits on its own `year` row, because PIP and WID rarely
    match the same observation year, so this collapses across rows and keeps the
    year that actually carried each value.
    """
    out = {}
    for col, (metric, src) in MEASURES.items():
        if col not in comp.columns:
            print(f"  note: {col} absent from the dataset — skipping")
            continue
        d = comp.loc[comp[col].notna(), ["country", "ref_year", "year", col]]
        # A country-ref_year should carry one observation per measure.
        dup = d.duplicated(["country", "ref_year"]).sum()
        assert dup == 0, f"{col}: {dup} duplicate country/ref-year rows"
        for r in d.itertuples():
            out.setdefault((r.country, r.ref_year), {})[f"{metric}_{src}"] = float(getattr(r, col))
            out[(r.country, r.ref_year)][f"year_{src}"] = int(r.year)
    return out


def gini_scatter(collapsed, posttax, regions):
    """PIP Gini against WID pre-tax and post-tax Gini, at the ~2019 observation."""
    pt = {(r.country, r.year): float(r.gini) for r in posttax.itertuples()}

    rows = []
    missing_region, missing_posttax = [], []
    for (country, ref_year), v in sorted(collapsed.items()):
        if ref_year != SCATTER_REF_YEAR:
            continue
        if "gini_pip" not in v or "gini_wid" not in v:
            continue  # the scatter needs both axes
        region = regions.get(country)
        if region is None:
            missing_region.append(country)
            continue
        wid_year = v.get("year_wid")
        w_post = pt.get((country, wid_year))
        if w_post is None:
            missing_posttax.append(country)
        pip_year, y = v.get("year_pip"), None
        # The tooltip shows one year; where the two sources matched different
        # observations, show both rather than implying they agree.
        y = pip_year if pip_year == wid_year else f"{pip_year}/{wid_year}"
        rows.append(
            {
                "c": country,
                "p": round(v["gini_pip"], 4),
                "wPre": round(v["gini_wid"], 4),
                "wPost": None if w_post is None else round(w_post, 4),
                "r": region,
                "y": y,
                "yPip": pip_year,
                "yWid": wid_year,
            }
        )

    if missing_region:
        print(f"  note: no region for {missing_region}")
    if missing_posttax:
        print(f"  note: no post-tax WID Gini for {len(missing_posttax)} countries: {missing_posttax[:6]}")
    n_post = sum(1 for r in rows if r["wPost"] is not None)
    print(f"  gini scatter: {len(rows)} countries ({n_post} with a post-tax value)")

    return {
        "meta": {
            "title": "Inequality is a lot higher in WID than in PIP",
            "reference_year": int(SCATTER_REF_YEAR),
            "n_countries": len(rows),
            "units": "Gini coefficient, 0-1",
            "notes": [
                f"Each country at its observation nearest {SCATTER_REF_YEAR}, as matched by "
                "the comparison dataset (at most five years away, preferring the same "
                "welfare concept and reporting level).",
                "PIP: disposable income or consumption, per capita. WID: national income, "
                "per adult, pre-tax and post-tax.",
                "`y` is the observation year; where PIP and WID matched different years it "
                "shows both, and yPip / yWid carry them separately.",
                "Source: garden/poverty_inequality/2025-01-22/inequality_comparison, with "
                "post-tax Gini from garden/wid/2026-06-18/world_inequality_database.",
            ],
            "generated_by": "25_fig_scatters_from_etl.py",
            "etl_version": es.COMPARISON_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.COMPARISON_VERSION}/inequality_comparison",
        },
        "countries": rows,
    }


def trend_scatter(collapsed, regions):
    """Four measures for each of 1993 and 2019, both sources — the trend and
    change scatters."""
    countries = sorted({c for c, _ in collapsed})
    rows = []
    for c in countries:
        rec = {"c": c, "r": regions.get(c)}
        any_value = False
        for ref_year, suffix in REF_YEARS.items():
            v = collapsed.get((c, ref_year), {})
            for metric in ("gini", "top10", "palma", "top1"):
                for src in ("pip", "wid"):
                    val = v.get(f"{metric}_{src}")
                    rec[f"{metric}_{src}{suffix}"] = None if val is None else round(val, 4)
                    any_value = any_value or val is not None
        if any_value and rec["r"] is not None:
            rows.append(rec)

    counts = {
        k: sum(1 for r in rows if r.get(k) is not None)
        for k in rows[0]
        if k not in ("c", "r")
    }
    print(f"  trend scatter: {len(rows)} countries")
    print(f"    non-null: gini pip/wid 1993 {counts['gini_pip93']}/{counts['gini_wid93']}, "
          f"2019 {counts['gini_pip19']}/{counts['gini_wid19']}, top1 pip/wid "
          f"{counts['top1_pip19']}/{counts['top1_wid19']}")
    both = sum(1 for r in rows if r["gini_pip93"] is not None and r["gini_wid93"] is not None)
    print(f"    countries with both sources in 1993: {both}")

    return {
        "meta": {
            "title": "How has income inequality changed since 1993?",
            "reference_years": [1993, 2019],
            "n_countries": len(rows),
            "units": "Gini 0-1; top-10% and top-1% shares in %; Palma is a ratio",
            "notes": [
                "Each country at its observations nearest 1993 and 2019, as matched by "
                "the comparison dataset.",
                "top1_pip is empty throughout: PIP publishes no top-1% share, so the "
                "PIP panel of a top-1% view is blank by design.",
                "PIP: disposable income or consumption, per capita. WID: pre-tax national "
                "income, per adult.",
                "Source: garden/poverty_inequality/2025-01-22/inequality_comparison.",
            ],
            "generated_by": "25_fig_scatters_from_etl.py",
            "etl_version": es.COMPARISON_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.COMPARISON_VERSION}/inequality_comparison",
        },
        "countries": rows,
    }


def write(obj, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    path.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"  wrote {name} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
