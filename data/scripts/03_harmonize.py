"""
03_harmonize.py — build the harmonized PIP + WID quantile dataset.

THE POINT OF THIS FILE
----------------------
Downstream analyses and deck figures need income distributions from both
sources in ONE tidy table with an IDENTICAL bin structure, so that any
statistic computed on one source can be computed on the other the same way.

PIP arrives as 1000 bins of 0.1% each; WID arrives as 109 bins (99 one-percent
bins, then the top 1% split into 9 tenth-of-a-percent bins plus the top 0.1%).
PIP's 0.1% bins nest exactly inside WID's bins, so we aggregate PIP to the
WID structure with zero approximation error:

    PIP quantiles  1-10    -> p0p1          (10 bins of 0.1% -> one 1% bin)
    ...
    PIP quantiles 981-990  -> p98p99
    PIP quantile  991      -> p99p99.1      (1:1)
    ...
    PIP quantile  999      -> p99.8p99.9    (1:1)
    PIP quantile  1000     -> p99.9p100     (1:1)

(An earlier version of this analysis aggregated PIP to 101 bins, collapsing
p99-p99.9 into a single bin, so PIP and WID had *different* top-end structures.
Matching WID's 109 bins exactly is deliberate: top-share statistics — e.g. the
top 1% and top 0.1% — are then computed on identical bins for both sources.)

Aggregation math: within each target bin, `avg` is the population-weighted
mean of the source bins' averages and `pop` is the sum of their populations.
PIP bins within a country hold equal population by construction, so this is
exact, not an approximation.

THE FIVE SERIES in the output ("source" column)
-----------------------------------------------
    PIP                      disposable income/consumption, PER CAPITA
                             (per-capita basis is inherent to PIP)
    WID_pretax_per_adult     pre-tax national income, per adult (WID native)
    WID_pretax_per_capita    ... converted to per capita (see 02_process_wid.py)
    WID_posttax_per_adult    post-tax NATIONAL income (DINA, code diinc), per adult
    WID_posttax_per_capita   ... converted to per capita

Note on concepts: WID's post-tax national income redistributes ALL taxes and
government spending, so it is still a broader concept than PIP's disposable
income/consumption (which, in WID terms, is closest to post-tax disposable
income, code cainc — not currently fetched). The headline published contrast
is PIP vs WID_pretax_*; which pair to show is an editorial choice that this
dataset leaves open.

The `pop` column is the population base matching the series: bin total
population for per-capita series (incl. PIP), bin adult population for
per-adult series. The `share` column is the bin's share of the country's
total income under that series (WID: as fetched; PIP: computed).

Zero incomes are RETAINED (they exist in WID's bottom percentiles); how to
treat them is an analysis decision, not a data-pipeline one.

INPUTS   data/raw/pip/pip_thousand_bins_2023.csv.gz   (01_fetch_pip.py)
         data/processed/wid_percentiles_2023.csv      (02_process_wid.py)
OUTPUT   data/processed/pip_wid_harmonized_2023.csv

Run:  python data/scripts/03_harmonize.py
"""

import numpy as np
import pandas as pd

from config import (
    PIP_RAW_FILE, WID_PROCESSED_FILE, HARMONIZED_FILE, PROCESSED_DIR,
    TARGET_YEAR, wid_bin_labels, fmt,
)


# ---------------------------------------------------------------------------
# PIP: aggregate 1000 bins -> the 109-bin WID structure
# ---------------------------------------------------------------------------

def pip_quantile_to_wid_bin(q):
    """Map a PIP quantile number (1..1000) to its WID bin label."""
    if q <= 990:
        i = (q - 1) // 10                      # 1-10 -> 0, 11-20 -> 1, ...
        return f"p{i}p{i + 1}"
    lo = round(99 + 0.1 * (q - 991), 1)        # 991 -> 99.0, 992 -> 99.1, ...
    hi = round(lo + 0.1, 1) if q < 1000 else 100
    return f"p{fmt(lo)}p{fmt(hi)}"


def aggregate_pip(pip):
    """Aggregate the 1000-bin PIP data to the 109 WID bins, exactly."""
    pip = pip.copy()
    pip["percentile"] = pip["quantile"].map(pip_quantile_to_wid_bin)

    # Population-weighted mean income and total population per target bin.
    pip["income_total"] = pip["avg"] * pip["pop"]
    g = pip.groupby(["country", "year", "percentile"], observed=True).agg(
        pop=("pop", "sum"),
        income_total=("income_total", "sum"),
    ).reset_index()
    g["average"] = g["income_total"] / g["pop"]

    # p_low / p_high from the bin label (single source of truth: the label)
    bounds = g["percentile"].str.removeprefix("p").str.split("p", expand=True).astype(float) / 100
    g["p_low"], g["p_high"] = bounds[0], bounds[1]

    # Income share of each bin within its country
    g["share"] = g["income_total"] / g.groupby("country", observed=True)["income_total"].transform("sum")

    g["source"] = "PIP"
    return g[["country", "year", "percentile", "p_low", "p_high", "pop", "average", "share", "source"]]


# ---------------------------------------------------------------------------
# WID: reshape the processed file into one block per series
# ---------------------------------------------------------------------------

WID_SERIES = [
    # (source label,            avg column,               share column,    pop column)
    ("WID_pretax_per_adult",   "avg_pretax_per_adult",   "share_pretax",  "bin_adult_pop"),
    ("WID_pretax_per_capita",  "avg_pretax_per_capita",  "share_pretax",  "bin_total_pop"),
    ("WID_posttax_per_adult",  "avg_posttax_per_adult",  "share_posttax", "bin_adult_pop"),
    ("WID_posttax_per_capita", "avg_posttax_per_capita", "share_posttax", "bin_total_pop"),
]


def reshape_wid(wid):
    blocks = []
    for label, avg_col, share_col, pop_col in WID_SERIES:
        block = wid[["country", "year", "percentile", "p_low", "p_high"]].copy()
        block["pop"] = wid[pop_col]
        block["average"] = wid[avg_col]
        block["share"] = wid[share_col]
        block["source"] = label
        n_missing = block["average"].isna().sum()
        if n_missing:
            # A bin with no value for this income concept can't enter the
            # series. Drop and report — never silently.
            missing_countries = block.loc[block["average"].isna(), "country"].nunique()
            print(f"  {label}: dropping {n_missing} bins with missing income "
                  f"(across {missing_countries} countries)")
            block = block.dropna(subset=["average"])
        blocks.append(block)
    return pd.concat(blocks, ignore_index=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    labels = wid_bin_labels()
    assert len(labels) == 109

    pip = pd.read_csv(PIP_RAW_FILE)
    wid = pd.read_csv(WID_PROCESSED_FILE)

    print(f"PIP raw: {len(pip):,} rows ({pip['country'].nunique()} countries)")
    print(f"WID processed: {len(wid):,} rows ({wid['country'].nunique()} countries)")

    # --- PIP ---
    pip_h = aggregate_pip(pip)
    assert (pip_h.groupby("country", observed=True).size() == 109).all(), \
        "PIP aggregation did not produce 109 bins per country"
    assert set(pip_h["percentile"]) == set(labels), "PIP bin labels do not match WID's"

    # --- WID ---
    assert set(wid["percentile"]) == set(labels), "WID bin labels unexpected"
    wid_h = reshape_wid(wid)

    # --- Combine ---
    out = pd.concat([pip_h, wid_h], ignore_index=True)
    # Stable, readable ordering
    out = out.sort_values(["source", "country", "p_low"]).reset_index(drop=True)
    out = out[["source", "country", "year", "percentile", "p_low", "p_high",
               "pop", "average", "share"]]

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(HARMONIZED_FILE, index=False)

    print(f"\nSaved: {HARMONIZED_FILE}")
    summary = out.groupby("source", observed=True).agg(
        countries=("country", "nunique"),
        rows=("percentile", "size"),
        total_pop_bn=("pop", lambda s: s.sum() / 1e9),
        mean_income=("average", lambda s: np.average(
            s, weights=out.loc[s.index, "pop"])),
    ).round(3)
    print(summary.to_string())


if __name__ == "__main__":
    main()
