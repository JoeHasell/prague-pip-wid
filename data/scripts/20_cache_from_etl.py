"""
20_cache_from_etl.py — refresh the committed ETL cache in data/raw/etl/.

This replaces the old stages 00-04 (the Stata WID fetch, the PIP download, the
harmonisation, the consumption->income fit). All of that now happens in OWID's
ETL; this script just pulls the results down and commits them, so every figure
script below runs offline. See etl_source.py for the full rationale.

WHAT IT CACHES (and why these, not everything)
----------------------------------------------
The ETL's bin-level table has 6.4M rows — far too large to commit, and the
figures do not need it. What they need is:

  inequality_decomposition             280 rows   the Q2 bars, every year+series
  inequality_decomposition_by_country  59k rows   per-country means / within-MLD
  inequality_change_by_reference_year  408 rows   the Q1 reference-year figure
  consumption_income_model             100 rows   the regression, for reference
  example_country_bins                 ~21k rows  the 109 bins of the three
                                                  example countries only, which
                                                  is what the Q2 lollipops plot

The last one is a SUBSET of income_distributions, filtered to the three example
countries; it is written under its own name to keep that clear.

USAGE
-----
    python data/scripts/20_cache_from_etl.py
        pull from the public OWID catalog (the permanent source).

    python data/scripts/20_cache_from_etl.py --staging <etl-branch>
        pull from an OWID staging server, for use while the ETL pull request
        that adds these datasets is still open. Internal network only.

After running, re-generate the figures:
    python data/scripts/21_fig_bridging_from_etl.py
    python data/scripts/22_fig_reference_year_trends.py
"""

import argparse
import sys

import etl_source as es

# Tables cached verbatim.
PLAIN_TABLES = [
    "inequality_decomposition",
    "inequality_decomposition_by_country",
    "inequality_change_by_reference_year",
    "consumption_income_model",
]

# Columns of the bin-level table the lollipop figure needs.
BIN_COLUMNS = ["country", "year", "series", "percentile", "p_low", "p_high", "pop", "avg"]

# The bins the lollipops read (P10, P90 and the two extremes) plus everything
# needed to compute a country mean: the mean is a population-weighted average
# over all 109 bins, so the full set is kept for the three example countries.
LOLLIPOP_BINS = ["p0p1", "p10p11", "p90p91", "p99.9p100"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument(
        "--staging",
        metavar="BRANCH",
        help="pull from staging-site-<BRANCH> instead of the public catalog",
    )
    args = ap.parse_args()

    source = "staging" if args.staging else "catalog"
    where = f"staging ({args.staging})" if args.staging else "the OWID catalog"
    print(f"Pulling ETL version {es.ETL_VERSION} from {where}\n")

    for table in PLAIN_TABLES:
        try:
            df = es.load(table, source=source, branch=args.staging)
        except Exception as e:  # noqa: BLE001 - report which table, then stop
            print(f"ERROR fetching {table}: {e}")
            print(
                "\nIf the ETL pull request is not merged yet, the catalog does not "
                "have these datasets. Use --staging <etl-branch>."
            )
            return 1
        path = es.write_cache(table, df)
        print(f"  {table:<38} {len(df):>7,} rows -> {path.name}")

    # The bin-level subset for the three example countries.
    bins = es.load("income_distributions", source=source, branch=args.staging, columns=BIN_COLUMNS)
    bins = bins[bins["country"].isin(es.EXAMPLE_COUNTRIES)].reset_index(drop=True)
    assert not bins.empty, "no rows for the example countries — check their names"
    counts = bins.groupby(["country", "year", "series"], observed=True).size()
    assert (counts == 109).all(), "example-country bins are not the full 109-bin structure"
    path = es.write_cache("example_country_bins", bins)
    print(f"  {'example_country_bins':<38} {len(bins):>7,} rows -> {path.name}")

    print(
        f"\nCached {bins['year'].min()}-{bins['year'].max()} for "
        f"{bins['series'].nunique()} series. Now re-run the figure scripts "
        f"(21_ and 22_)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
