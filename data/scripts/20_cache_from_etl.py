"""
20_cache_from_etl.py — refresh the committed ETL cache in data/raw/etl/.

This replaces the old stages 00-04 (the Stata WID fetch, the PIP download, the
harmonisation, the consumption->income fit). All of that now happens in OWID's
ETL; this script pulls the results down and commits them, so every figure script
below runs offline. See etl_source.py for the full rationale.

WHAT IT CACHES (and why these, not everything)
----------------------------------------------
The ETL's bin-level table has 6.4M rows across 1990-2024 — too large to commit,
and the figures do not need all of it. What they need is:

  inequality_decomposition             280 rows   the Q2 bars, every year+series
  inequality_decomposition_by_country  59k rows   per-country means / within-MLD
  inequality_change_by_reference_year  408 rows   the Q1 reference-year figure
  consumption_income_model             100 rows   the per-percentile regression
  example_country_bins                 92k rows   the 109 bins of the three
                                                  example countries, all years
  display_year_bins                   184k rows   all countries x all series x
                                                  109 bins, for ONE year — the
                                                  top-thresholds, treemap and
                                                  top-adjustment figures
  pip_dual_percentiles                 14k rows   PIP income/consumption
                                                  percentiles for the
                                                  consumption->income explainer
  inequality_comparison               438 rows    PIP vs WID Gini, top-10% share,
                                                  Palma and (WID only) top-1%
                                                  share at the matched 1993 and
                                                  2019 observations
  wid_posttax_gini                    ~34k rows   WID post-tax Gini, the second
                                                  y-axis on the Gini scatter
  pip_observed_inequality             ~2.4k rows  PIP's published measures at the
                                                  years it actually surveyed
  wid_observed_inequality             ~14k rows   WID's published measures, minus
                                                  its extrapolated country-years
  country_regions                      ~220 rows  World Bank region per country
  treemap_regions                      ~220 rows  the treemap's eight-region grouping,
                                                  built from PIP's regions plus a
                                                  Western Europe split

The scatter slides read `inequality_comparison` rather than recomputing their
measures from the bins. That dataset already does the reference-year matching
(nearest observation to 1993 / 2019, preferring the same welfare concept and
reporting level), and it is the dataset those slides were originally built from —
so refreshing from it is a like-for-like update rather than a redefinition. It is
also why the top-1% panel is blank for PIP: PIP publishes no top-1% share.

USAGE
-----
    python data/scripts/20_cache_from_etl.py
        pull from the public OWID catalog (the permanent source).

    python data/scripts/20_cache_from_etl.py --staging <etl-branch>
        pull from an OWID staging server, for use while the ETL pull request
        that adds these datasets is still open. Internal network only.

    python data/scripts/20_cache_from_etl.py --skip-heavy
        refresh only the small tables, leaving the bin-derived ones alone.

After running, re-generate the figures:
    python data/scripts/21_fig_bridging_from_etl.py
    python data/scripts/22_fig_reference_year_trends.py
    python data/scripts/23_fig_explainers_from_etl.py
    python data/scripts/24_fig_top_of_distribution_from_etl.py
    python data/scripts/25_fig_scatters_from_etl.py
"""

import argparse
import sys

import numpy as np

import etl_source as es

# Tables cached verbatim from the ETL.
PLAIN_TABLES = [
    "inequality_decomposition",
    "inequality_decomposition_by_country",
    "inequality_change_by_reference_year",
    "consumption_income_model",
]

BIN_COLUMNS = ["country", "year", "series", "percentile", "p_low", "p_high", "pop", "avg"]

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--staging", metavar="BRANCH", help="pull from staging-site-<BRANCH>")
    ap.add_argument("--skip-heavy", action="store_true", help="skip the bin-derived tables")
    args = ap.parse_args()

    source = "staging" if args.staging else "catalog"
    where = f"staging ({args.staging})" if args.staging else "the OWID catalog"
    print(f"Pulling ETL version {es.ETL_VERSION} from {where}\n")

    for table in PLAIN_TABLES:
        try:
            df = es.load(table, source=source, branch=args.staging)
        except Exception as e:  # noqa: BLE001 - name the table, then stop
            print(f"ERROR fetching {table}: {e}")
            print(
                "\nIf the ETL pull request is not merged yet, the catalog does not have "
                "these datasets. Use --staging <etl-branch>."
            )
            return 1
        print(f"  {table:<38} {len(df):>7,} rows -> {es.write_cache(table, df).name}")

    if args.skip_heavy:
        print("\n--skip-heavy: leaving the bin-derived tables as they are.")
        return 0

    # ------------------------------------------------------------------
    # The bin-level table. Read once; three cache tables come out of it.
    # ------------------------------------------------------------------
    print("\nReading the bin-level distributions (large: ~6.4M rows)…")
    bins = es.load("income_distributions", source=source, branch=args.staging, columns=BIN_COLUMNS)
    bins["year"] = bins["year"].astype(int)
    for c in ("p_low", "p_high", "pop", "avg"):
        bins[c] = bins[c].astype(np.float64)
    years = sorted(bins["year"].unique())
    print(f"  {len(bins):,} rows, {years[0]}-{years[-1]}, {bins['country'].nunique()} countries")

    # 1. The three example countries, every year (the per-country Q2 figure).
    ex = bins[bins["country"].isin(es.EXAMPLE_COUNTRIES)].reset_index(drop=True)
    assert not ex.empty, "no rows for the example countries — check their names"
    check_full_bins(ex, "example_country_bins")
    print(f"  {'example_country_bins':<38} {len(ex):>7,} rows -> {es.write_cache('example_country_bins', ex).name}")

    # 2. One year, every country and series (top-of-distribution + explainers).
    year = es.DISPLAY_YEAR if es.DISPLAY_YEAR in years else years[-1]
    dy = bins[bins["year"] == year].reset_index(drop=True)
    check_full_bins(dy, "display_year_bins")
    print(f"  {'display_year_bins':<38} {len(dy):>7,} rows -> {es.write_cache('display_year_bins', dy).name}  (year {year})")

    # ------------------------------------------------------------------
    # PIP's own percentiles (the consumption->income explainer), the cross-source
    # comparison table (the scatters), and the regions used to colour countries.
    # ------------------------------------------------------------------
    print("\nReading the comparison dataset, PIP percentiles and regions from the OWID catalog…")
    dual = es.load_pip_dual_percentiles()
    print(f"  {'pip_dual_percentiles':<38} {len(dual):>7,} rows -> {es.write_cache('pip_dual_percentiles', dual).name}")

    comp = es.load_inequality_comparison()
    print(f"  {'inequality_comparison':<38} {len(comp):>7,} rows -> {es.write_cache('inequality_comparison', comp).name}")

    posttax = es.load_wid_posttax_gini()
    print(f"  {'wid_posttax_gini':<38} {len(posttax):>7,} rows -> {es.write_cache('wid_posttax_gini', posttax).name}")

    regions = es.load_country_regions()
    print(f"  {'country_regions':<38} {len(regions):>7,} rows -> {es.write_cache('country_regions', regions).name}")

    pip_obs = es.load_pip_observed_inequality()
    print(f"  {'pip_observed_inequality':<38} {len(pip_obs):>7,} rows -> "
          f"{es.write_cache('pip_observed_inequality', pip_obs).name}")

    wid_obs = es.load_wid_observed_inequality()
    print(f"  {'wid_observed_inequality':<38} {len(wid_obs):>7,} rows -> "
          f"{es.write_cache('wid_observed_inequality', wid_obs).name}")

    treemap_regions = es.load_treemap_regions()
    print(f"  {'treemap_regions':<38} {len(treemap_regions):>7,} rows -> "
          f"{es.write_cache('treemap_regions', treemap_regions).name}")

    print("\nDone. Now re-run the figure scripts (21_ through 25_).")
    return 0


def check_full_bins(df, name):
    """Every (country, year, series) group must carry the full 109-bin structure."""
    counts = df.groupby(["country", "year", "series"], observed=True).size()
    bad = counts[counts != 109]
    assert bad.empty, f"{name}: {len(bad)} groups without 109 bins, e.g. {bad.head(3).to_dict()}"


if __name__ == "__main__":
    sys.exit(main())
