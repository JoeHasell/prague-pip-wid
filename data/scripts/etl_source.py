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
    the WID percentile distributions for every year, already converted to
    international dollars (see THE PRICE BASIS below).
  - the numbers are computed once, in a pipeline whose sanity checks gate the
    build, rather than twice in two places that can drift apart.
  - every figure covers 1990-2024 instead of 2023 alone, because the ETL runs
    the whole panel. The charts expose that as a year control.

This module is the only place that knows where that data comes from.

THE PRICE BASIS OF WHAT COMES BACK
----------------------------------
Everything this module returns is in PPP international dollars, but the two
sources sit on different PRICE BASES. Stating it precisely, because earlier
versions of these notes got it wrong:

    PIP   2021 PPP round, 2021 prices
    WID   2021 PPP round, 2025 prices     <- note the price base, not the round

The PPP ROUND is the same for both. WID's `xlcusp` factors, re-expressed at a
2021 price base, reproduce the World Bank's published 2021 PPP conversion
factors (PA.NUS.PPP) for 184 of 197 countries to within 0.01%. Any claim that
the two sources use "different PPP rounds" or "different PPP vintages" is
wrong; the difference is the price base alone.

WID arrives at 2025 prices because WID publishes incomes in constant local
currency of the LATEST year in the database (currently 2025), and `xlcusp(Y)`
converts local currency already at year-Y prices. The ETL extracts WID in
2025-price LCU and converts with `xlcusp(2025)`. Checked against WID's own LCU
series: US national income per capita 2023 is 71,410.28/yr in the ETL cache
against 71,410.40/yr computed independently.

So: every value in data/raw/etl/ and every data/figures/fig_*.json is in
2021-PPP international dollars AT 2025 PRICES.

WHY IT IS LEFT AT 2025 PRICES
-----------------------------
Putting WID on PIP's 2021-price basis was investigated on 2026-09-08 and NOT
adopted: the deck stays on 2025-price WID. It would have taken a single scalar
(x0.854244, the US national income price index for 2021) because international
dollars are US-price-denominated, so re-basing one is only US deflation — the
country's own inflation cancels against xlcusp. Nothing relative would have
moved; the one substantive change was the means scatter. The proper home for
such a fix is the ETL itself, not a scalar applied here — see WHY THIS EXISTS
above, and the reasoning in data/README.md.

WHAT THIS MEANS WHEN READING THE DATA: any comparison of WID LEVELS against PIP
LEVELS inherits the four-year price gap — WID values are ~17% higher than a
like-for-like comparison would put them. Relative measures (MLD, Gini, shares)
are unaffected, since a price base is a uniform rescale.

Full write-up: data/README.md, "Prices, PPPs and the two price bases".

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

WHERE THE DATA COMES FROM (four tiers, in order)
------------------------------------------------
  1. the public OWID catalog — the permanent home. The datasets landed there with
     owid/etl#6764 (merged 2026-09-02), so this is the normal path and needs no VPN;
  2. an OWID staging server — only while a FUTURE ETL pull request changes these
     datasets and they exist there before merging (internal network only, and
     ephemeral: the server is torn down when the branch is merged or deleted);
  3. a LOCAL ETL checkout's data directory (`--local <path to owid/etl>`) — the
     same feather files a staging server serves, read straight from disk. For an
     ETL developer who has built the branch locally; it also outlives a staging
     server that has been torn down. Say which build it was in the commit;
  4. the committed cache in data/raw/etl/ — written by 20_cache_from_etl.py.

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
    python data/scripts/refresh_from_etl.py --local <path to a built owid/etl checkout>

Nothing here watches the ETL: until the refresh runs, the deck renders whatever
was cached last.
"""

import gzip
import json
from pathlib import Path

import numpy as np
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
#   reference_year_bins   PIP and WID post-tax per capita at every PIP SURVEY
#                         country-year — enough for load_bins() to rebuild the
#                         PIP-side chain in any year (33_reference_year_indicators.py).
#   wid_reference_year_indicators
#                         Gini / shares / Palma of the two WID per-capita series
#                         at EVERY country-year, computed at cache time by
#                         refyears.indicators_from_bins on the deck's grid: the
#                         1.6M WID bin rows behind them are too large to commit.
CACHE_ONLY_TABLES = {
    "pip_observed_inequality",
    "wid_observed_inequality",
    "example_country_bins",
    "display_year_bins",
    "reference_year_bins",
    "wid_reference_year_indicators",
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

# The World Bank PIP release the figures read directly from the catalog. Named once
# here so a version bump cannot leave one URL — or a figure's stated provenance —
# behind.
PIP_VERSION = "2026-06-26"
PIP_DATASET = ("wb", PIP_VERSION, "world_bank_pip")

# Two other OWID datasets the figures draw on directly. Both are long published,
# so these read from the public catalog rather than needing the staging fallback.
PIP_PERCENTILES_URL = (
    f"https://catalog.ourworldindata.org/garden/wb/{PIP_VERSION}/world_bank_pip/percentiles.parquet"
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

# The price base of the WID side of everything this module returns. WID
# publishes in constant LCU of the latest database year and the ETL converts
# with xlcusp of that same year, so WID values are 2021-PPP international
# dollars AT 2025 PRICES while PIP is at 2021 prices. Re-check against
# wid.world's "Prices and currency conversions in WID.world" note after any WID
# refresh: if WID's latest year moves, this moves with it.
WID_PRICE_BASE_YEAR = 2025

# WHICH top-1% method the deck's own PIP_topadj uses. THE deck-wide baseline:
# every figure that shows PIP_topadj (and WID_posttax_rescaled, whose means are
# forced onto it) reads it from here, so this one line moves the whole deck.
#
#   "match"  — under-reporting: PIP's own top 1% is rescaled until its income
#              share equals WID's. Expressible on the percentile grid, so the whole
#              pipeline downstream is unaffected.
#   "append" — under-representation: the survey IS the bottom 99% and a new top
#              percentile is appended (Anand & Segal 2015). This lands OFF the
#              percentile grid, so it cannot currently be the bridging column
#              without a re-binning step that does not exist yet. It appears in
#              the eight-scenario comparison instead.
#
# Joe chose "append" on 2026-09-09, on the merits: the under-representation
# story is the one the deck tells, and it is the only method it now reports.
#
# CONSEQUENCE — PIP_topadj IS RAGGED. Append re-reads the survey as the bottom
# 99%, so its bins land at ranks the percentile grid does not have: 101 bins for
# an adjusted country, DECK_BINS for one the gate skipped. Its bin LABELS are
# rewritten to the ranks they actually occupy, so any lookup written for the grid
# fails loudly. Read it by rank window, and decompose it with expect_bins=None.
# Every other series in the frame — including WID_posttax_rescaled, which takes
# only its country MEANS from PIP_topadj — stays on the grid.
TOPADJ_METHOD = "append"

# THE DECK'S ANALYTICAL GRID (2026-09-09): 100 PERCENTILE BINS.
# The ETL publishes 109 bins — 99 one-percent bins, nine 0.1% bins across
# p99-p99.9, and the top 0.1%. load_bins() collapses those ten into ONE 1%-wide
# bin at their population-weighted mean, before anything else is built, so every
# analytical series in the deck sits on a plain percentile grid.
#
# WHY. The extra resolution bought almost nothing and cost a lot of friction: it
# made the top adjustment's output awkward to express, produced charts with ten
# identical points pretending to be resolution, and forced bin-label lookups that
# break the moment a series is re-ranked. Measured before the change, collapsing
# it moves the MLD decompositions by at most 0.3pp on any between share, and the
# BETWEEN components not at all — aggregation preserves each country's total
# income and population, so country means are untouched by construction.
#
# WHAT IT COSTS. Anything genuinely about the top 0.1% — the top-of-distribution
# thresholds figure (24) — must read the RAW loader, es.load(), which still
# returns the ETL's own 109 bins. Only load_bins() applies this convention.
DECK_BINS = 100


def aggregate_to_percentiles(bins):
    """Collapse each (series, country, year)'s top 1% into one 1%-wide bin.

    Preserves total income and population exactly, so means, top-1% shares and
    the between-country component are unchanged; only dispersion INSIDE the top
    1% is given up.
    """
    m = bins["p_low"].to_numpy(dtype=float) >= TOP1_START - RANK_EPS
    keep, top = bins[~m], bins[m]
    grp = ["series", "country", "year"]
    inc = (top["avg"].to_numpy(float) * top["pop"].to_numpy(float))
    agg = top.assign(_inc=inc).groupby(grp, observed=True).agg(
        pop=("pop", "sum"), _inc=("_inc", "sum")).reset_index()
    agg["avg"] = agg["_inc"] / agg["pop"]
    agg = agg.drop(columns="_inc")
    agg["p_low"], agg["p_high"] = TOP1_START, 1.0
    agg["percentile"] = TOP1_LABEL
    out = pd.concat([keep, agg[keep.columns.intersection(agg.columns)]],
                    ignore_index=True, sort=False)
    for col in keep.columns:
        if col not in out.columns:
            out[col] = np.nan
    return out[keep.columns].sort_values(grp + ["p_low"], ignore_index=True)


TOP1_START = 0.99          # where the top 1% begins; mirrors topadj.TOP1_START
TOP1_LABEL = "p99p100"
# Tolerance for rank tests. The ETL stores p_low / p_high as FLOAT32, so a rank
# arrives as e.g. 0.8999999761581421 for p90p91: a test against 0.9 with a 1e-9
# slack silently drops that bin, and 0.99 only survives because float32 happens
# to round it UP. Anything comparing ranks uses this, or integrates over a rank
# window instead (refyears.window_income).
RANK_EPS = 1e-6

# Each source's own published inequality measures. Used by the observation-matched
# reference-year figures, which only ever read a country-year the source actually
# surveyed or observed — never an interpolated or extrapolated one.
PIP_INEQUALITY_URL = (
    f"https://catalog.ourworldindata.org/garden/wb/{PIP_VERSION}/world_bank_pip/inequality.parquet"
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


def garden_url(namespace, version, dataset, table, source="catalog", branch=None, root=None):
    """URL (or local path) of any garden table.

    The catalog serves parquet and feather; a staging server serves the ETL data
    directory as it sits on disk, which is feather; a local ETL checkout (`root`)
    holds that same directory under data/garden/. `read_garden` picks the reader.
    """
    if source == "staging":
        assert branch, "source='staging' needs the ETL branch name"
        return (
            f"http://staging-site-{branch}:{STAGING_PORT}/garden/"
            f"{namespace}/{version}/{dataset}/{table}.feather"
        )
    if source == "local":
        assert root, "source='local' needs the path to an owid/etl checkout"
        return str(Path(root) / "data" / "garden" / namespace / version / dataset / f"{table}.feather")
    assert source == "catalog", f"unknown source: {source}"
    return f"{CATALOG_ROOT}/{namespace}/{version}/{dataset}/{table}.parquet"


def read_garden(url, columns=None):
    """Read a garden table from a catalog (parquet) or staging / local (feather) URL.

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
        if not url.startswith("http"):
            raise RuntimeError(
                f"{url} is not in that ETL checkout.\n"
                "`--local` reads a checkout's data/garden/ directory, so the dataset must have been "
                "built there (etlr) at the version pinned in etl_source.py."
            ) from e
        raise


def catalog_url(table):
    """Public OWID catalog URL of one ETL table."""
    return f"{CATALOG_BASE}/{ETL_VERSION}/{TABLES[table]}/{table}.feather"


def staging_url(table, branch):
    """URL of one ETL table on the staging server of an OWID branch."""
    return garden_url("poverty_inequality", ETL_VERSION, TABLES[table], table,
                      source="staging", branch=branch)


def local_url(table, root):
    """Path of one ETL table inside a local owid/etl checkout's data directory."""
    return garden_url("poverty_inequality", ETL_VERSION, TABLES[table], table,
                      source="local", root=root)


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


def load_bins(table, source="cache", branch=None):
    """Bins for a figure, with PIP_consinc rebuilt on the deck's own method.

    THE GRID IS 100 PERCENTILE BINS. The ETL's ten 0.1% bins across the top 1%
    are collapsed FIRST, before anything is rebuilt, so every series in the
    returned frame — the ETL's own as well as the ones rebuilt here — sits on the
    same plain percentile grid. See DECK_BINS above for why, and use the raw
    load() if you need the ETL's own resolution.

    The ETL builds PIP_consinc with a per-percentile log-log regression fitted on
    PIP's 88 dual country-years. Since 2026-09-09 this project instead uses WID's
    scaled-logit correction profile with WID's own parameters — see consinc.py for
    the method, the reasoning, and why PIP's dual pairs are not a usable
    estimation sample. Everything else in the frame is passed through untouched.
    """
    import consinc, rescale, topadj

    bins = aggregate_to_percentiles(load(table, source=source, branch=branch))
    basis = load("pip_welfare_basis", source=source, branch=branch)

    # The PIP-side chain is rebuilt END TO END, because each step feeds the next:
    # PIP_consinc -> PIP_topadj (the top-1% method) -> WID_posttax_rescaled
    # (whose country means are forced onto PIP_topadj). Rebuilding only the first
    # would leave the other two paired with the ETL's superseded version.
    untouched = ~bins["series"].isin(["PIP_consinc", "PIP_topadj", "WID_posttax_rescaled"])
    out = [bins[untouched]]
    for y in sorted(bins["year"].unique()):
        gy = bins[bins["year"] == y]
        by = basis[basis["year"] == y]
        wt = dict(zip(by["country"], by["welfare_type"]))
        ci = consinc.build_pip_consinc_profile(gy, wt)
        ta = topadj.build_top1(pd.concat([gy[untouched[gy.index]], ci], ignore_index=True),
                               TOPADJ_METHOD, out_series="PIP_topadj",
                               grid=TOPADJ_METHOD != "append")
        rs = rescale.build_from_bins(pd.concat([gy[untouched[gy.index]], ta], ignore_index=True),
                                     mean_source="PIP_topadj")
        out += [ci, ta, rs]
    res = pd.concat(out, ignore_index=True)

    # Guards. The conversion is a pure per-rank rescaling, so: income countries
    # must be untouched, consumption countries must differ from PIP by exactly
    # the profile, and the bin structure must be intact.
    pip = bins[bins["series"] == "PIP"].set_index(["country", "year", "percentile"])
    ci = res[res["series"] == "PIP_consinc"].set_index(["country", "year", "percentile"])
    common = pip.index.intersection(ci.index)
    assert len(common) == len(ci), "PIP_consinc lost or gained bins"
    # Every series must be on the grid, except PIP_topadj when the top-1% method
    # is one that re-ranks (see TOPADJ_METHOD above).
    ragged = {"PIP_topadj"} if TOPADJ_METHOD == "append" else set()
    n_bins = res[~res["series"].isin(ragged)].groupby(
        ["series", "country", "year"], observed=True).size()
    assert (n_bins == DECK_BINS).all(), \
        f"not on the {DECK_BINS}-bin grid: {n_bins[n_bins != DECK_BINS].head(3).to_dict()}"
    ratio = (ci.loc[common, "avg"] / pip.loc[common, "avg"]).to_numpy(float)
    mid = ((pip.loc[common, "p_low"] + pip.loc[common, "p_high"]) / 2).to_numpy(float)
    expected = consinc.correction_profile(mid)
    # Welfare basis is per COUNTRY-YEAR: a country can switch between the two.
    wtype = dict(zip(zip(basis["country"], basis["year"]), basis["welfare_type"]))
    is_income = np.array([wtype.get((c, y)) != "consumption" for c, y, _ in common])
    assert np.allclose(ratio[is_income], 1.0, rtol=1e-9), \
        "income-basis countries should pass through unchanged"
    assert np.allclose(ratio[~is_income], expected[~is_income], rtol=1e-6), \
        "consumption countries do not match the correction profile"
    return res


def load(table, source="cache", branch=None, columns=None, root=None):
    """Return one ETL table as a DataFrame, with deck series names.

    source="cache"    read the committed cache (default: offline and reproducible).
    source="catalog"  read the public OWID catalog.
    source="staging"  read an OWID staging server (needs `branch`).
    source="local"    read a local owid/etl checkout's data directory (needs `root`).
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

    if source == "staging":
        url = staging_url(table, branch)
    elif source == "local":
        url = local_url(table, root)
    else:
        url = catalog_url(table)
    df = read_garden(url, columns=columns)
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


def load_inequality_comparison(source="catalog", branch=None, root=None):
    """The cross-source comparison table: PIP and WID pre-tax Gini, top-10% share,
    Palma and (WID only) top-1% share, at the matched 1993 and 2019 observations."""
    df = read_garden(garden_url(*COMPARISON_DATASET, "inequality_comparison",
                                source=source, branch=branch, root=root))
    for c in ("country", "ref_year", "reference_years", "only_all_series"):
        df[c] = df[c].astype(str)
    df["year"] = df["year"].astype(int)
    return df.reset_index(drop=True)


def load_wid_posttax_gini(first_year=1985, source="catalog", branch=None, root=None):
    """WID's post-tax national income Gini, with extrapolations — the second
    y-axis on the Gini scatter."""
    df = read_garden(
        garden_url(*WID_DATASET, "inequality", source=source, branch=branch, root=root),
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


def load_wid_observed_inequality(source="catalog", branch=None, root=None):
    """WID's published inequality measures, excluding the country-years WID does not
    rate as directly supported by data.

    Both tax concepts are kept, tagged by `welfare`, so the figures can show pre-tax
    and post-tax side by side. Since wid/2026-09-02 the `extrapolated = "no"` slice is
    defined by WID's own 0-5 data-quality score rather than by its retired
    extrapolation flag, so this is a wider set than it used to be.
    """
    df = read_garden(
        garden_url(*WID_DATASET, "inequality", source=source, branch=branch, root=root),
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
