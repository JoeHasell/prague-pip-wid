"""
22_fig_reference_year_trends.py — data for the Q1 "varying reference year" figure.

THE FIGURE (rendered by components/fig-reference-year-trends.js)
---------------------------------------------------------------
This is the figure sketched by hand on the three "Varying reference year..."
slides. For each REFERENCE YEAR on the x axis, compared against the latest year
in the data, it answers:

  - in how many countries has inequality risen / fallen / stayed stable?
  - what share of the covered population lives in each group?
  - what was the average change, unweighted and population-weighted?

with PIP on the left and WID on the right, and a metric selector covering the
Gini plus three Generalized Entropy indices. The GE parameter alpha sets how
sensitive the index is to the top versus the bottom of the distribution, which
is the "top vs bottom sensitivity" the sketch asks for:

    GE(0) = mean log deviation   bottom-sensitive
    GE(1) = Theil index          scale-neutral
    GE(2)                        top-sensitive

Every metric is computed by OWID's ETL from the SAME 109-bin distributions for
both sources, so PIP and WID are compared on identical definitions rather than
through each source's own published headline measure.

METHOD NOTES (all decided in the ETL step, recorded here for the chart)
----------------------------------------------------------------------
  - "stable" means the metric changed by no more than +-5% in relative terms
    between the reference year and the latest year; beyond that it counts as
    rising or falling. The band is a parameter of the ETL step.
  - population shares use each country's population in the LATEST year, so the
    reading is "x% of people alive today live in a country where inequality has
    risen since <reference year>".
  - the country sample is identical for every reference year (a balanced panel),
    which is what makes the counts comparable along the x axis.
  - GE(0) needs a floor for zero-income bins (log of zero is undefined); the ETL
    uses $0.01/day. That floor is doing real work on the WID PRE-TAX series
    only — see the note in the JSON meta.

INPUT   the ETL cache (data/raw/etl/), via etl_source.py
OUTPUT  data/figures/fig_reference_year_trends.json

Run:  python data/scripts/22_fig_reference_year_trends.py
"""

import json
from pathlib import Path

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_reference_year_trends.json"

# The three series the figure compares, and how to label them.
SERIES = [
    {"key": "PIP", "label": "PIP", "sub": "disposable income or consumption, per capita"},
    {"key": "WID_pretax_per_adult", "label": "WID — pre-tax", "sub": "national income, per adult"},
    {"key": "WID_posttax_per_adult", "label": "WID — post-tax", "sub": "national income, per adult"},
]

# Metric keys as the ETL names them, with display labels and the alpha they
# correspond to (None for the Gini, which is not a GE index).
METRICS = [
    {"key": "gini", "label": "Gini coefficient", "alpha": None,
     "note": "Standard inequality index, 0 = everyone equal."},
    {"key": "mean_log_deviation", "label": "Mean log deviation — GE(0)", "alpha": 0,
     "note": "Bottom-sensitive: gives most weight to changes at the bottom of the distribution."},
    {"key": "theil_index", "label": "Theil index — GE(1)", "alpha": 1,
     "note": "Scale-neutral member of the Generalized Entropy family."},
    {"key": "generalized_entropy_2", "label": "GE(2)", "alpha": 2,
     "note": "Top-sensitive: gives most weight to changes at the top of the distribution."},
]


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    tb = es.load("inequality_change_by_reference_year")

    wanted = {s["key"] for s in SERIES}
    tb = tb[tb["series"].isin(wanted)]
    assert not tb.empty, f"none of {wanted} present — check the series mapping"

    latest_year = int(tb["latest_year"].iloc[0])
    years = sorted(int(y) for y in tb["year"].unique())
    n_countries = int(tb["num_countries"].iloc[0])
    print(f"  reference years {years[0]}-{years[-1]}, compared against {latest_year}")
    print(f"  {n_countries} countries, {tb['metric'].nunique()} metrics, {tb['series'].nunique()} series")

    # series -> metric -> per-reference-year records, kept compact for the browser.
    data = {}
    for s in SERIES:
        per_metric = {}
        for m in METRICS:
            d = tb[(tb["series"] == s["key"]) & (tb["metric"] == m["key"])].sort_values("year")
            if d.empty:
                continue
            per_metric[m["key"]] = {
                "year": [int(v) for v in d["year"]],
                "rising": [int(v) for v in d["num_countries_rising"]],
                "falling": [int(v) for v in d["num_countries_falling"]],
                "stable": [int(v) for v in d["num_countries_stable"]],
                "pop_rising": [round(float(v), 5) for v in d["population_share_rising"]],
                "pop_falling": [round(float(v), 5) for v in d["population_share_falling"]],
                "pop_stable": [round(float(v), 5) for v in d["population_share_stable"]],
                "avg_change": [round(float(v), 6) for v in d["average_change"]],
                "avg_change_pw": [round(float(v), 6) for v in d["average_change_population_weighted"]],
                "avg_rel_change": [round(float(v), 6) for v in d["average_relative_change"]],
                "avg_rel_change_pw": [
                    round(float(v), 6) for v in d["average_relative_change_population_weighted"]
                ],
            }
        data[s["key"]] = per_metric

    out = {
        "meta": {
            "title": "Varying the reference year: where has inequality risen since?",
            "latest_year": latest_year,
            "years": years,
            "n_countries": n_countries,
            "series": SERIES,
            "metrics": METRICS,
            "stable_threshold": 0.05,
            "etl_version": es.ETL_VERSION,
            "etl_dataset": (
                f"garden/poverty_inequality/{es.ETL_VERSION}/inequality_trends_by_reference_year"
            ),
            "units": "counts of countries; population shares of the covered sample",
            "notes": [
                f"Each point compares the reference year on the x axis with {latest_year}.",
                "A country counts as stable when the metric changed by 5% or less in "
                "relative terms; beyond that it is rising or falling.",
                f"Population shares use each country's population in {latest_year}, and "
                f"cover the {n_countries} countries present in both sources.",
                "The country sample is identical for every reference year, so the counts "
                "are comparable along the x axis.",
                "All metrics are computed from the same harmonised 109-bin distributions, "
                "so PIP and WID are compared on identical definitions.",
                "GE(0) (the mean log deviation) needs a floor for zero-income bins. The "
                "ETL uses $0.01/day. This affects the WID PRE-TAX series materially — "
                "the bottom ~5 percentiles are zero in most countries — and the PIP "
                "series not at all (it has no zero bins).",
                f"{latest_year} is a nowcast/extrapolated year on both sides.",
            ],
            "generated_by": "data/scripts/22_fig_reference_year_trends.py",
        },
        "data": data,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nSaved: {OUTPUT_FILE.name} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")

    # Report the headline the figure will show, so a run is self-checking.
    print(f"\nGini, since {years[0]} (rising / falling / stable, and population rising):")
    for s in SERIES:
        g = data[s["key"]].get("gini")
        if not g:
            continue
        i = g["year"].index(years[0])
        print(
            f"  {s['label']:<16} {g['rising'][i]:3d} / {g['falling'][i]:3d} / {g['stable'][i]:3d}"
            f"   ({g['pop_rising'][i]:.0%} of population)"
        )


if __name__ == "__main__":
    main()
