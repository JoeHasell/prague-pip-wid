"""
26_fig_reference_year_observed.py — the reference-year figures, on OBSERVED data only.

An alternative to 22_fig_reference_year_trends.py, for the same three slides.

WHY BOTH EXIST
--------------
22_ reads the harmonised 109-bin panel, which is complete: every country has a
value for every year from 1990 to 2024. That gives 211 countries at every
reference year, but most of those country-years are not observations — 73% of the
WID side is WID's own extrapolation, and the 2024 endpoint the chart compares
against is 97% extrapolated. The counts are then partly a statement about
extrapolation rather than about measured inequality.

This script instead applies the method the Gini and trend scatters use: for each
country and each reference year, take the source's NEAREST ACTUAL OBSERVATION
within a window, and use nothing at all if there isn't one. Coverage drops a long
way and varies by reference year — which is the honest shape of the evidence.

    22_  complete panel      211 countries everywhere, mostly extrapolated
    26_  observed only       coverage varies by year, every point a real survey

Neither is "the right one": the first shows the fullest picture the sources can be
made to give, the second shows only what they actually measured. The deck can
carry both and say which is which.

WHAT COUNTS AS OBSERVED
-----------------------
  PIP  a survey in its headline consolidated series (no comparability spells);
       the intra/extrapolated table is not used.
  WID  a country-year it does not flag as extrapolated.

Measures are each source's OWN published Gini, top-10% share, top-1% share and
Palma — the same basis as the scatter slides — rather than the bin-computed
versions 22_ uses. One difference worth noting: PIP publishes a top-1% share, so
unlike the trend scatters this figure can show a PIP top-1% panel.

OUTPUT  data/figures/fig_reference_year_observed.json
        (same shape as fig_reference_year_trends.json, so the same two components
        render it — the slides just pass a different dataUrl)

Run:  python data/scripts/26_fig_reference_year_observed.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_reference_year_observed.json"

# How far from a reference year an observation may sit and still be used. Five
# years is the window the comparison dataset behind the scatter slides uses.
MAX_DISTANCE = 5

# The year every reference year is compared against. Later years have very little
# observed data on the WID side, so this is deliberately not the last year in the
# data — it is the latest year with enough observations to compare against.
LATEST_YEAR = 2019
FIRST_REFERENCE_YEAR = 1990

# Matching the trend figure's band, so the two are read the same way.
STABLE_THRESHOLD = 0.05

SERIES = [
    {"key": "PIP", "label": "PIP", "sub": "disposable income or consumption, per capita"},
    {"key": "WID_pretax_per_adult", "label": "WID — pre-tax", "sub": "national income, per adult"},
    {"key": "WID_posttax_per_adult", "label": "WID — post-tax", "sub": "national income, per adult"},
]

METRICS = [
    {"key": "gini", "label": "Gini coefficient", "alpha": None,
     "note": "Each source's own published Gini, at observed years only."},
    {"key": "top10_share", "label": "Top 10% share", "alpha": None,
     "note": "Share of income going to the richest 10%, as published."},
    {"key": "top1_share", "label": "Top 1% share", "alpha": None,
     "note": "Share of income going to the richest 1%, as published."},
    {"key": "palma", "label": "Palma ratio", "alpha": None,
     "note": "Top 10% share divided by the bottom 40% share."},
]
METRIC_KEYS = [m["key"] for m in METRICS]


def main():
    print("Reading the ETL cache")
    pip = es.load("pip_observed_inequality")
    wid = es.load("wid_observed_inequality")
    weights = es.load("inequality_decomposition_by_country")

    observed = {
        "PIP": pip[["country", "year"] + METRIC_KEYS],
        "WID_pretax_per_adult": wid.loc[wid["welfare"] == "before tax", ["country", "year"] + METRIC_KEYS],
        "WID_posttax_per_adult": wid.loc[wid["welfare"] == "after tax", ["country", "year"] + METRIC_KEYS],
    }
    for k, v in observed.items():
        print(f"  {k:<24} {len(v):>6,} observations, {v['country'].nunique():>3} countries")

    population = latest_population(weights)
    ref_years = list(range(FIRST_REFERENCE_YEAR, LATEST_YEAR))

    data = {}
    coverage = {}
    for s in SERIES:
        obs = observed[s["key"]]
        latest = match(obs, LATEST_YEAR)
        per_metric = {}
        for metric in METRIC_KEYS:
            rows = []
            for y in ref_years:
                earlier = match(obs, y)
                rows.append(compare(earlier, latest, metric, y, population))
            per_metric[metric] = {
                "year": ref_years,
                **{
                    field: [r[field] for r in rows]
                    for field in (
                        "rising", "falling", "stable", "pop_rising", "pop_falling", "pop_stable",
                        "avg_change", "avg_change_pw", "avg_rel_change", "avg_rel_change_pw",
                        "n_countries",
                    )
                },
            }
        data[s["key"]] = per_metric
        n = per_metric["gini"]["n_countries"]
        coverage[s["key"]] = n
        print(f"  {s['key']:<24} countries per reference year (Gini): "
              f"min {min(n)}, median {int(np.median(n))}, max {max(n)}")

    # The stacked-count panels scale to one number, so use the largest coverage
    # any reference year reaches. Shorter stacks then read as thinner evidence,
    # which is the point of this variant.
    max_countries = max(max(v) for v in coverage.values())

    out = {
        "meta": {
            "title": "Varying the reference year — observed data only",
            "latest_year": LATEST_YEAR,
            "years": ref_years,
            "n_countries": max_countries,
            "series": SERIES,
            "metrics": METRICS,
            "stable_threshold": STABLE_THRESHOLD,
            "max_distance_years": MAX_DISTANCE,
            "etl_version": es.COMPARISON_VERSION,
            "etl_dataset": (
                "garden/wb/2026-06-26/world_bank_pip#inequality and "
                "garden/wid/2026-06-18/world_inequality_database#inequality"
            ),
            "units": "counts of countries; population shares of the countries covered",
            "notes": [
                f"Every point uses each source's nearest ACTUAL observation within "
                f"{MAX_DISTANCE} years of the reference year, and of {LATEST_YEAR}. Countries "
                "without one on both sides of the comparison are left out entirely.",
                "Coverage therefore varies by reference year, and the stacked panels are "
                f"scaled to the largest coverage reached ({max_countries} countries) — a "
                "shorter stack means fewer countries had observations that far back.",
                "PIP: surveys in its consolidated headline series, no comparability spells. "
                "WID: country-years it does not flag as extrapolated.",
                "Measures are each source's own published ones, the same basis as the "
                "cross-source scatter slides.",
                f"Compared against {LATEST_YEAR} rather than the last year in the data, "
                "because later years have very little observed WID data.",
                "The companion figure (fig_reference_year_trends.json) instead uses the "
                "complete harmonised panel: many more countries, but mostly extrapolated.",
            ],
            "generated_by": "26_fig_reference_year_observed.py",
        },
        "data": data,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nSaved: {OUTPUT_FILE.name} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")

    g = data["PIP"]["gini"]
    i = g["year"].index(1990)
    print(f"\nGini since 1990, compared with {LATEST_YEAR} (rising / falling / stable, countries):")
    for s in SERIES:
        gg = data[s["key"]]["gini"]
        print(f"  {s['label']:<16} {gg['rising'][i]:3d} / {gg['falling'][i]:3d} / {gg['stable'][i]:3d}"
              f"   of {gg['n_countries'][i]:3d} with observations")


def match(obs, target_year):
    """Each country's observation nearest `target_year`, within MAX_DISTANCE.

    Ties go to the earlier year, which is what the comparison dataset behind the
    scatter slides does.
    """
    d = obs[(obs["year"] >= target_year - MAX_DISTANCE) & (obs["year"] <= target_year + MAX_DISTANCE)].copy()
    d["distance"] = (d["year"] - target_year).abs()
    d = d.sort_values(["country", "distance", "year"])
    return d.groupby("country", as_index=False).first()


def compare(earlier, latest, metric, ref_year, population):
    """Counts, population shares and average changes for one reference year."""
    a = earlier[["country", metric]].rename(columns={metric: "then"})
    b = latest[["country", metric]].rename(columns={metric: "now"})
    j = a.merge(b, on="country", how="inner").dropna(subset=["then", "now"])
    j = j[j["then"] != 0]
    j = j.merge(population, on="country", how="inner")

    if j.empty:
        return {k: 0 for k in ("rising", "falling", "stable", "n_countries")} | {
            k: 0.0 for k in ("pop_rising", "pop_falling", "pop_stable", "avg_change",
                             "avg_change_pw", "avg_rel_change", "avg_rel_change_pw")
        }

    change = j["now"] - j["then"]
    rel = change / j["then"]
    rising, falling = rel > STABLE_THRESHOLD, rel < -STABLE_THRESHOLD
    stable = ~rising & ~falling
    pop = j["population"].to_numpy(float)
    total = pop.sum()

    return {
        "n_countries": int(len(j)),
        "rising": int(rising.sum()),
        "falling": int(falling.sum()),
        "stable": int(stable.sum()),
        "pop_rising": round(float(pop[rising.to_numpy()].sum() / total), 5),
        "pop_falling": round(float(pop[falling.to_numpy()].sum() / total), 5),
        "pop_stable": round(float(pop[stable.to_numpy()].sum() / total), 5),
        "avg_change": round(float(change.mean()), 6),
        "avg_change_pw": round(float(np.average(change, weights=pop)), 6),
        "avg_rel_change": round(float(rel.mean()), 6),
        "avg_rel_change_pw": round(float(np.average(rel, weights=pop)), 6),
    }


# The cache carries the deck's own series names, not the ETL's.
POPULATION_SERIES = "WID_pretax_per_capita"


def latest_population(weights):
    """Country population for weighting — WID's total population, as elsewhere."""
    y = weights["year"].max()
    d = weights[(weights["year"] == y) & (weights["series"] == POPULATION_SERIES)]
    assert not d.empty, f"no population rows for {POPULATION_SERIES} in {y}"
    return d[["country", "population_weight"]].rename(columns={"population_weight": "population"})


if __name__ == "__main__":
    main()
