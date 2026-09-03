"""
etl_source.py — THE contract between this deck and Our World in Data's ETL.

WHY THIS EXISTS
---------------
The methodology behind the Q1 and Q2 figures — harmonising PIP and WID onto one
109-bin structure, the three bridging series, the between/within MLD
decomposition, the Gini/GE metrics — used to live in this repo, in scripts
00-04 plus the method modules (mld.py, topadj.py, rescale.py, consinc.py).
It has since been ported into OWID's ETL as two versioned garden datasets, so
that:

  - it re-runs automatically on every PIP and WID data update. (This repo's PIP
    extract is pinned to catalog version 2025-10-13; the World Bank has since
    published a revision, in which 15 countries' 2023 means move by more than
    5% — Bosnia -30%, Turkey +20%, Germany -9%. The global bars barely move,
    but individual countries do.)
  - it needs no local Stata run. The WID fetch took 1-2 hours; the ETL holds
    the WID percentile distributions for every year, already PPP-converted.
  - the numbers are computed once, in a pipeline whose sanity checks gate the
    build, rather than twice in two places that can drift apart.
  - every figure covers 1990-2024 instead of 2023 alone, because the ETL runs
    the whole panel. The charts expose that as a year control.

This module is the only place that knows where that data comes from.

THE TWO ETL DATASETS
--------------------
  poverty_inequality/<ETL_VERSION>/harmonized_income_distributions
      income_distributions                 109-bin distributions, 8 series
      inequality_decomposition             between/within MLD per year+series
      inequality_decomposition_by_country  per-country means and within-MLD
      consumption_income_model             the per-percentile regression
      pip_welfare_basis                    income vs consumption per country-year
  poverty_inequality/<ETL_VERSION>/inequality_trends_by_reference_year
      inequality_metrics                   Gini/GE(0)/GE(1)/GE(2) per country-year
      inequality_change_by_reference_year  rising/falling/stable per reference year

WHERE THE DATA COMES FROM (three tiers, in order)
-------------------------------------------------
  1. the public OWID catalog — the permanent home. The datasets landed there with
     owid/etl#6764 (merged 2026-09-02), so this is the normal path and needs no VPN;
  2. an OWID staging server — only while a FUTURE ETL pull request changes these
     datasets and they exist there before merging (internal network only, and
     ephemeral: the server is torn down when the branch is merged or deleted);
  3. the committed cache in data/raw/etl/ — written by 20_cache_from_etl.py.

All four datasets the figures read follow those tiers: the two harmonized ones above,
plus `inequality_comparison` and the WID dataset itself (the scatters' post-tax Gini
and the observed-only reference-year slides). The other inputs — PIP's percentiles and
inequality, the thousand-bins regions, OWID's regions — are long published and always
come from the catalog.

The figure scripts use the cache by default, so they run offline and the deck
builds reproducibly on any machine — exactly like the PIP extract committed in
data/raw/pip/. The cache is small (the figure inputs, not the 6.4M-row bin
table).

Refresh the cache AND every figure in one command (see refresh_from_etl.py):

    python data/scripts/refresh_from_etl.py

    # only while an ETL pull request that changes these datasets is still open:
    python data/scripts/refresh_from_etl.py --staging <owid/etl branch name>

Nothing here watches the ETL: until the refresh runs, the deck renders whatever
was cached last.
"""

import gzip
import json
from pathlib import Path

import pandas as pd

# Version of both ETL datasets (they are versioned together).
ETL_VERSION = "2026-08-25"

CATALOG_ROOT = "https://catalog.ourworldindata.org/garden"
CATALOG_BASE = f"{CATALOG_ROOT}/poverty_inequality"
STAGING_PORT = 8881

# table name -> the ETL dataset it belongs to
TABLES = {
    "income_distributions": "harmonized_income_distributions",
    "inequality_decomposition": "harmonized_income_distributions",
    "inequality_decomposition_by_country": "harmonized_income_distributions",
    "consumption_income_model": "harmonized_income_distributions",
    "pip_welfare_basis": "harmonized_income_distributions",
    "inequality_metrics": "inequality_trends_by_reference_year",
    "inequality_change_by_reference_year": "inequality_trends_by_reference_year",
}

CACHE_DIR = Path(__file__).resolve().parents[1] / "raw" / "etl"

# Cached subsets that are DERIVED from an ETL table rather than being one. They
# exist only in the cache; 20_cache_from_etl.py builds them.
#   example_country_bins  the 109 bins of the three example countries, from
#                         income_distributions (whose 6.4M rows are too large
#                         to commit and unnecessary for the figures).
CACHE_ONLY_TABLES = {
    "pip_observed_inequality",
    "wid_observed_inequality",
    "example_country_bins",
    "display_year_bins",
    "pip_dual_percentiles",
    "country_regions",
    "inequality_comparison",
    "wid_posttax_gini",
    "treemap_regions",
}

# ---------------------------------------------------------------------------
# Series names
# ---------------------------------------------------------------------------
# The ETL spells its series names out; this deck's components — and the
# `sources` prop in content/slides.json — use the shorter original names. The
# figure JSONs keep the DECK names, so no slide or component needs editing.
ETL_TO_DECK_SERIES = {
    "wid_before_tax_per_adult": "WID_pretax_per_adult",
    "wid_before_tax_per_capita": "WID_pretax_per_capita",
    "wid_after_tax_per_adult": "WID_posttax_per_adult",
    "wid_after_tax_per_capita": "WID_posttax_per_capita",
    "wid_after_tax_rescaled": "WID_posttax_rescaled",
    "pip_income_basis_top_adjusted": "PIP_topadj",
    "pip_income_basis": "PIP_consinc",
    "pip": "PIP",
}

# Labels written into the figure JSONs' meta.sources (kept verbatim from the
# original figure scripts, so the JSON contract is unchanged).
DECK_SERIES_LABELS = {
    "WID_pretax_per_adult": "WID (pre-tax national income, per adult)",
    "WID_pretax_per_capita": "WID (pre-tax national income, per capita)",
    "WID_posttax_per_adult": "WID (post-tax national income, per adult)",
    "WID_posttax_per_capita": "WID (post-tax national income, per capita)",
    "WID_posttax_rescaled": (
        "WID post-tax, rescaled to the ADJUSTED PIP country means (shape from WID, "
        "level from PIP_topadj — the far end of the PIP-side chain — so the "
        "bridge meets in the middle)"
    ),
    "PIP_topadj": (
        "PIP on an income basis, top-adjusted (WID post-tax shape grafted above the "
        "splice bin, applied ON TOP of the consumption->income adjustment)"
    ),
    "PIP_consinc": (
        "PIP adjusted to an income basis (consumption countries mapped via the "
        "dual-country regression)"
    ),
    "PIP": "PIP (disposable income or consumption, per capita)",
}

# Bridging order for the Q2 figures (WID side -> meeting point -> PIP side).
BRIDGING_ORDER = [
    "WID_pretax_per_adult",
    "WID_pretax_per_capita",
    "WID_posttax_per_adult",
    "WID_posttax_per_capita",
    "PIP",
    "PIP_topadj",
    "WID_posttax_rescaled",
    "PIP_consinc",
]

# The three example countries used by the per-country Q2 figure.
EXAMPLE_COUNTRIES = ["United States", "Indonesia", "Nigeria"]

# Displayed incomes are PER MONTH; the ETL's unit is international-$ per day.
DAILY_TO_MONTHLY = 365 / 12

# The single year the top-of-distribution and explainer figures show.
DISPLAY_YEAR = 2023

# Two other OWID datasets the figures draw on directly. Both are long published,
# so these read from the public catalog rather than needing the staging fallback.
PIP_PERCENTILES_URL = (
    "https://catalog.ourworldindata.org/garden/wb/2026-06-26/world_bank_pip/percentiles.parquet"
)
OWID_REGIONS_URL = (
    "https://catalog.ourworldindata.org/garden/regions/2023-01-01/regions/regions.parquet"
)
# The treemap groups countries into eight regions. Seven of them are PIP's own
# current scheme, which the ETL carries on the thousand-bins table. The eighth is a
# Western Europe split out of PIP's "Europe and Central Asia" — a grouping PIP does
# not make, and which this project has always drawn by hand.
#
# It is built here from the closest published definition plus the three places the
# project's own grouping departs from it, rather than from a pasted list, so the
# departures are visible and the names are checked against the data every run.
#
# Base: IHME GBD's "Western Europe" — the right concept (high-income Western
# Europe, as against post-socialist Eastern Europe and Central Asia), and the
# closest of the ETL's definitions to this project's list.
WESTERN_EUROPE_DEFINITION = "Western Europe (IHME GBD)"
# Dependent territories follow their sovereign: PIP reports a few separately
# (Greenland, Gibraltar, the Isle of Man, the Faroe Islands), and they belong with
# the country they depend on.
WESTERN_EUROPE_INCLUDE_TERRITORIES = True
# Where this project's grouping differs from the base definition:
#   Channel Islands  PIP reports Guernsey and Jersey as one aggregate, which the
#                    territory lists name individually.
#   Liechtenstein    a Western European micro-state the base definition omits.
WESTERN_EUROPE_ADD = {"Channel Islands", "Liechtenstein"}
#   Cyprus           the base definition counts it as Western Europe; this project
#                    groups it with Eastern Europe and Central Asia.
WESTERN_EUROPE_REMOVE = {"Cyprus"}
EUROPE_PARENT = "Europe and Central Asia"
EUROPE_REMAINDER = "Eastern Europe and Central Asia"

THOUSAND_BINS_URL = (
    "https://catalog.ourworldindata.org/garden/wb/2026-03-25/"
    "thousand_bins_distribution/thousand_bins_distribution.parquet"
)
PIP_PPP_VERSION = 2021

# Each source's own published inequality measures. Used by the observation-matched
# reference-year figures, which only ever read a country-year the source actually
# surveyed or observed — never an interpolated or extrapolated one.
PIP_INEQUALITY_URL = (
    "https://catalog.ourworldindata.org/garden/wb/2026-06-26/world_bank_pip/inequality.parquet"
)
# PIP's headline series: surveys consolidated across welfare types, no comparability
# spells. The "intra/extrapolated" table is deliberately NOT used.
PIP_TABLE = "Income or consumption consolidated"
PIP_SPELLS = "No spells"

# The cross-source comparison dataset behind the Gini and trend scatters. It does
# the reference-year matching (nearest observation to 1993 / 2019, preferring the
# same welfare concept and reporting level), which is why those slides read from
# it rather than from the bin-level distributions.
COMPARISON_VERSION = "2025-01-22"
COMPARISON_DATASET = ("poverty_inequality", COMPARISON_VERSION, "inequality_comparison")
# Post-tax WID Gini is not in the comparison dataset (which carries pre-tax only),
# so it comes from the WID dataset itself.
# Bump this with the WID version. 2026-06-18 was removed from the ETL when 2026-09-02 landed, so a
# stale version here points at a path that is no longer maintained.
#
# This version is NOT in the public catalog until owid/etl#6806 merges, so a catalog refresh will
# fail on it until then — use `--staging <that PR's branch>`, which is what the committed cache was
# built from.
WID_VERSION = "2026-09-02"
WID_DATASET = ("wid", WID_VERSION, "world_inequality_database")

# The deck's scatter legend spells this region with "the"; PIP does not.
REGION_RELABEL = {"Latin America and Caribbean": "Latin America and the Caribbean"}


def garden_url(namespace, version, dataset, table, source="catalog", branch=None):
    """URL of any garden table, from the public catalog or a branch's staging server.

    The catalog serves parquet and feather; a staging server serves the ETL data
    directory as it sits on disk, which is feather. `read_garden` picks the reader.
    """
    if source == "staging":
        assert branch, "source='staging' needs the ETL branch name"
        return (
            f"http://staging-site-{branch}:{STAGING_PORT}/garden/"
            f"{namespace}/{version}/{dataset}/{table}.feather"
        )
    assert source == "catalog", f"unknown source: {source}"
    return f"{CATALOG_ROOT}/{namespace}/{version}/{dataset}/{table}.parquet"


def read_garden(url, columns=None):
    """Read a garden table from a catalog (parquet) or staging (feather) URL.

    A missing catalog path almost always means the ETL version pinned above is not published
    yet — the pyarrow error for that is unhelpful, so say what to do instead.
    """
    reader = pd.read_feather if url.endswith(".feather") else pd.read_parquet
    try:
        return reader(url, columns=columns)
    except (FileNotFoundError, OSError) as e:
        if url.startswith(CATALOG_ROOT):
            raise RuntimeError(
                f"{url} is not in the public OWID catalog.\n"
                "A version pinned in etl_source.py is probably still on an unmerged ETL branch. "
                "Refresh with `--staging <that branch>` (internal network only), which is how the "
                "committed cache in data/raw/etl/ was built; a plain catalog refresh works once "
                "the ETL pull request merges."
            ) from e
        raise


def catalog_url(table):
    """Public OWID catalog URL of one ETL table."""
    return f"{CATALOG_BASE}/{ETL_VERSION}/{TABLES[table]}/{table}.feather"


def staging_url(table, branch):
    """URL of one ETL table on the staging server of an OWID branch."""
    return garden_url("poverty_inequality", ETL_VERSION, TABLES[table], table,
                      source="staging", branch=branch)


def cache_path(table):
    """Committed cache file for one ETL table."""
    return CACHE_DIR / f"{table}.csv.gz"


def _to_deck_series(df):
    # `series` arrives from the ETL as a Categorical; cast to plain strings so the
    # rename is not rejected for introducing categories the dtype does not know.
    if "series" in df.columns:
        raw = df["series"].astype(str)
        df["series"] = raw.map(ETL_TO_DECK_SERIES).fillna(raw)
    # Categoricals become plain strings for predictable filtering. `percentile` is
    # a bin LABEL ("p0p1") in the distribution tables but an integer in the
    # regression model, so only non-numeric ones are cast.
    for col in ("country", "metric", "welfare_type", "series"):
        if col in df.columns:
            df[col] = df[col].astype(str)
    if "percentile" in df.columns and not pd.api.types.is_numeric_dtype(df["percentile"]):
        df["percentile"] = df["percentile"].astype(str)
    return df


def load(table, source="cache", branch=None, columns=None):
    """Return one ETL table as a DataFrame, with deck series names.

    source="cache"    read the committed cache (default: offline and reproducible).
    source="catalog"  read the public OWID catalog.
    source="staging"  read an OWID staging server (needs `branch`).
    """
    if table in CACHE_ONLY_TABLES:
        assert source == "cache", f"{table} is a derived cache subset; it has no {source} URL"
    else:
        assert table in TABLES, f"unknown ETL table: {table}"

    if source == "cache":
        path = cache_path(table)
        if not path.exists():
            raise RuntimeError(
                f"No cache at {path}. Run:  python data/scripts/20_cache_from_etl.py"
            )
        df = pd.read_csv(path, keep_default_na=False, na_values=[""])
        if columns:
            df = df[columns]
        return _to_deck_series(df)

    url = staging_url(table, branch) if source == "staging" else catalog_url(table)
    df = pd.read_feather(url, columns=columns)
    return _to_deck_series(df)


def write_cache(table, df):
    """Write one table to the committed cache (deck series names included)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path(table)
    with gzip.open(path, "wt", newline="") as f:
        df.to_csv(f, index=False)
    return path


def load_pip_dual_percentiles():
    """PIP's own income/consumption percentiles, at each country's most recent year.

    Feeds the consumption->income explainer, which is drawn at PIP's native
    100-percentile resolution rather than the deck's 109-bin structure. Where a
    country has a year with BOTH welfare types that year is preferred, so the
    chart can show the fit against an actual income series; otherwise its most
    recent consumption year is used.
    """
    df = pd.read_parquet(
        PIP_PERCENTILES_URL,
        columns=["country", "year", "ppp_version", "welfare_type", "reporting_level", "percentile", "avg"],
    )
    d = df[
        (df["ppp_version"] == PIP_PPP_VERSION)
        & (df["reporting_level"] == "national")
        & df["welfare_type"].isin(["income", "consumption"])
    ][["country", "year", "welfare_type", "percentile", "avg"]].copy()
    for c in ("country", "welfare_type"):
        d[c] = d[c].astype(str)
    d["year"] = d["year"].astype(int)
    d["avg"] = d["avg"].astype("float64")

    cons = d[d["welfare_type"] == "consumption"]
    latest = cons.groupby("country")["year"].max()
    both = d.groupby(["country", "year"])["welfare_type"].nunique()
    dual_latest = both[both == 2].reset_index().groupby("country")["year"].max()
    chosen = latest.copy()
    chosen.update(dual_latest)

    keep = d.merge(chosen.rename("chosen").reset_index(), on="country")
    keep = keep[keep["year"] == keep["chosen"]].drop(columns="chosen")
    return keep.sort_values(["country", "welfare_type", "percentile"]).reset_index(drop=True)


def load_country_regions():
    """World Bank region per country, from the thousand-bins distribution.

    Uses PIP's OLD region scheme (`region_old`), which is the seven-group one the
    scatter's palette and legend are built on — it keeps "Other high income
    countries" as a group, where the current scheme splits out North America. The
    treemap keeps the project's own modified scheme in data/raw/regions/ instead.
    """
    df = pd.read_parquet(THOUSAND_BINS_URL, columns=["country", "year", "region_old"])
    df["country"] = df["country"].astype(str)
    df["region"] = df["region_old"].astype(str).replace(REGION_RELABEL)
    latest = df.sort_values("year").groupby("country", as_index=False).last()
    return latest[["country", "region"]].sort_values("country").reset_index(drop=True)


def load_inequality_comparison(source="catalog", branch=None):
    """The cross-source comparison table: PIP and WID pre-tax Gini, top-10% share,
    Palma and (WID only) top-1% share, at the matched 1993 and 2019 observations."""
    df = read_garden(garden_url(*COMPARISON_DATASET, "inequality_comparison",
                                source=source, branch=branch))
    for c in ("country", "ref_year", "reference_years", "only_all_series"):
        df[c] = df[c].astype(str)
    df["year"] = df["year"].astype(int)
    return df.reset_index(drop=True)


def load_wid_posttax_gini(first_year=1985, source="catalog", branch=None):
    """WID's post-tax national income Gini, with extrapolations — the second
    y-axis on the Gini scatter."""
    df = read_garden(
        garden_url(*WID_DATASET, "inequality", source=source, branch=branch),
        columns=["country", "year", "welfare_type", "extrapolated", "gini"],
    )
    for c in ("country", "welfare_type", "extrapolated"):
        df[c] = df[c].astype(str)
    df["year"] = df["year"].astype(int)
    d = df[
        (df["welfare_type"] == "after tax")
        & (df["extrapolated"] == "yes")
        & (df["year"] >= first_year)
        & df["gini"].notna()
    ][["country", "year", "gini"]].copy()
    d["gini"] = d["gini"].astype("float64")
    return d.sort_values(["country", "year"]).reset_index(drop=True)


def load_treemap_regions():
    """The eight-region grouping the top-1% treemap colours by, from ETL sources.

    Seven groups are PIP's current scheme as published on the thousand-bins table.
    The eighth splits Western Europe out of PIP's "Europe and Central Asia": the
    membership of `WESTERN_EUROPE_DEFINITION` from OWID's regions dataset, plus the
    dependent territories of those members, plus the explicit adjustments above.
    What remains of PIP's Europe group is relabelled "Eastern Europe and Central
    Asia".

    This replaces the hand-maintained data/raw/regions/country_region_mapping.csv,
    and reproduces its grouping exactly for every country PIP covers — asserted
    below against that file while it is still present.
    """
    bins = pd.read_parquet(THOUSAND_BINS_URL, columns=["country", "year", "region"])
    bins["country"] = bins["country"].astype(str)
    bins["region"] = bins["region"].astype(str)
    latest = bins.sort_values("year").groupby("country", as_index=False).last()[["country", "region"]]

    regions = pd.read_parquet(OWID_REGIONS_URL, columns=["code", "name", "members", "related"])
    regions["name"] = regions["name"].astype(str)
    code_to_name = dict(zip(regions["code"].astype(str), regions["name"]))

    def names_from(col, region_name):
        row = regions[regions["name"] == region_name]
        assert len(row) == 1, f"{region_name} not found in the regions dataset"
        raw = row.iloc[0][col]
        if not isinstance(raw, str) or not raw:
            return set()
        return {code_to_name.get(c, c) for c in json.loads(raw)}

    west = names_from("members", WESTERN_EUROPE_DEFINITION)
    if WESTERN_EUROPE_INCLUDE_TERRITORIES:
        for member in list(west):
            west |= names_from("related", member)
    west = (west | WESTERN_EUROPE_ADD) - WESTERN_EUROPE_REMOVE

    in_europe = latest["region"] == EUROPE_PARENT
    latest["region"] = latest["region"].where(~in_europe, EUROPE_REMAINDER)
    latest.loc[in_europe & latest["country"].isin(west), "region"] = "Western Europe"

    n_groups = latest["region"].nunique()
    assert n_groups == 8, f"expected 8 region groups, got {n_groups}"

    # While the original mapping is still in the repo, prove this reproduces it for
    # every country PIP covers. (Its remaining entries are countries PIP has no
    # data for, so they never reach a figure.)
    legacy = CACHE_DIR.parents[1] / "raw" / "regions" / "country_region_mapping.csv"
    if legacy.exists():
        old = pd.read_csv(legacy)
        merged = latest.merge(old, on="country", how="inner", suffixes=("_new", "_old"))
        differ = merged[merged["region_new"] != merged["region_old"]]
        assert differ.empty, (
            "region grouping differs from the original mapping for: "
            + ", ".join(f"{r.country} ({r.region_old} -> {r.region_new})" for r in differ.itertuples())
        )

    return latest.sort_values("country").reset_index(drop=True)


def load_pip_observed_inequality():
    """PIP's published inequality measures at the years it actually surveyed.

    Top 10% is the sum of PIP's two top components (the 90-99 band plus the top 1%),
    because PIP publishes those rather than a single decile-10 share.
    """
    df = pd.read_parquet(
        PIP_INEQUALITY_URL,
        columns=["country", "year", "table", "survey_comparability", "gini", "palma_ratio",
                 "top90_99_share", "top1_share"],
    )
    for c in ("country", "table", "survey_comparability"):
        df[c] = df[c].astype(str)
    d = df[(df["table"] == PIP_TABLE) & (df["survey_comparability"] == PIP_SPELLS)].copy()
    d = d[d["gini"].notna()]
    d["year"] = d["year"].astype(int)
    d["gini"] = d["gini"].astype("float64")
    d["palma"] = d["palma_ratio"].astype("float64")
    d["top10_share"] = d["top90_99_share"].astype("float64") + d["top1_share"].astype("float64")
    d["top1_share"] = d["top1_share"].astype("float64")
    out = d[["country", "year", "gini", "top10_share", "top1_share", "palma"]]
    return out.sort_values(["country", "year"]).reset_index(drop=True)


def load_wid_observed_inequality(source="catalog", branch=None):
    """WID's published inequality measures, excluding the country-years WID does not
    rate as directly supported by data.

    Both tax concepts are kept, tagged by `welfare`, so the figures can show pre-tax
    and post-tax side by side. Since wid/2026-09-02 the `extrapolated = "no"` slice is
    defined by WID's own 0-5 data-quality score rather than by its retired
    extrapolation flag, so this is a wider set than it used to be.
    """
    df = read_garden(
        garden_url(*WID_DATASET, "inequality", source=source, branch=branch),
        columns=["country", "year", "welfare_type", "extrapolated", "gini", "palma_ratio",
                 "share_top_10", "share_top_1"],
    )
    for c in ("country", "welfare_type", "extrapolated"):
        df[c] = df[c].astype(str)
    d = df[
        (df["extrapolated"] == "no")
        & df["welfare_type"].isin(["before tax", "after tax"])
        & df["gini"].notna()
    ].copy()
    d["year"] = d["year"].astype(int)
    d = d.rename(columns={"welfare_type": "welfare", "palma_ratio": "palma",
                          "share_top_10": "top10_share", "share_top_1": "top1_share"})
    for c in ("gini", "palma", "top10_share", "top1_share"):
        d[c] = d[c].astype("float64")
    out = d[["country", "year", "welfare", "gini", "top10_share", "top1_share", "palma"]]
    return out.sort_values(["country", "welfare", "year"]).reset_index(drop=True)
