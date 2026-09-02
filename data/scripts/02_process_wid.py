"""
02_process_wid.py — convert raw WID percentile data to daily international
dollars, on both a per-adult and a per-capita basis.

INPUT (data/raw/wid/, produced by 00_fetch_wid.py)
--------------------------------------------------
WID_percentiles.csv        one row per country x percentile bin (109 bins),
                           year 2023. Income values are ANNUAL amounts in
                           LOCAL CURRENCY, per adult ("equal-split adults":
                           household income divided equally among adult
                           members). Two income concepts:
                             avg_pretax  / share_pretax   : pre-tax national income (WID code ptinc)
                             avg_posttax / share_posttax  : post-tax national income (WID code diinc)
                           diinc is the DINA post-tax concept: ALL taxes and
                           government spending are redistributed, so a
                           country's post-tax total equals its pre-tax
                           national income total (this identity is verified
                           in 99_verify.py). It is NOT disposable/cash income
                           (that is WID code cainc, not fetched).
WID_ppp.csv                PPP conversion factors (WID code xlcusp): local
                           currency units per international dollar. Contains BOTH 2023 and
                           2025; the pipeline uses PPP_YEAR (2025) — WID's price base.
WID_aggregate_population.csv   adult_pop (age 20+, WID age code 992) and
                           total_pop (all ages, code 999) per country, 2023.

TRANSFORMATIONS (each is a documented, deliberate step)
-------------------------------------------------------
1. PPP conversion:   local currency -> international dollars   (divide by ppp)
   *** This step was the source of a critical bug in an earlier version of
   this analysis (income left in local currency inflated Iran's top incomes
   to $200m/day). The step is verified by unit tests in 99_verify.py. ***
2. Annual -> daily:  divide by 365, to match PIP's daily amounts.
3. Per adult -> per capita: WID divides household income among ADULTS only;
   PIP divides among EVERYONE (incl. children). To put the two on a common
   per-capita basis:  avg_per_capita = avg_per_adult * adult_pop / total_pop.
   (This assumes the adult/child ratio is the same across the income
   distribution within a country — the standard simple adjustment.)
   We keep BOTH versions; the harmonized file exposes each as its own series.
4. Bin populations:  the raw file has no population column. Each bin spans
   (p_high - p_low) of the distribution, so:
       bin_adult_pop = adult_pop * (p_high - p_low)   [per-adult series]
       bin_total_pop = total_pop * (p_high - p_low)   [per-capita series]

WHAT THIS SCRIPT DOES *NOT* DO
------------------------------
- No zero-income handling. 921 pre-tax and 184 post-tax bin averages are
  exactly 0 (bottom ~5 percentiles in most countries). How to treat them
  (e.g. replace with $0.01/day before computing MLD) is an ANALYSIS decision
  and belongs in the analysis scripts, not the data pipeline.
- No country filtering beyond the fetch itself (211 countries with a PIP
  counterpart were fetched).

OUTPUT
------
data/processed/wid_percentiles_2023.csv — one row per country x bin, with
income in daily 2021-PPP-comparable international dollars* on both bases.

* WID PPPs are for 2023; PIP uses 2021 PPPs. Both are "international dollars"
  but from different PPP rounds — one of the known level differences between
  the sources (documented in data/README.md).

Run:  python data/scripts/02_process_wid.py
"""

import sys
import pandas as pd

from config import (
    WID_PERCENTILES_RAW, WID_PPP_FILE, WID_POPULATION_FILE,
    COUNTRY_MAPPING_FILE, WID_PROCESSED_FILE, PROCESSED_DIR, TARGET_YEAR,
    PPP_YEAR,
)

DAYS_PER_YEAR = 365


def main():
    # ------------------------------------------------------------------
    # Load raw inputs
    # ------------------------------------------------------------------
    pct = pd.read_csv(WID_PERCENTILES_RAW)
    ppp = pd.read_csv(WID_PPP_FILE)
    pop = pd.read_csv(WID_POPULATION_FILE)
    cmap = pd.read_csv(COUNTRY_MAPPING_FILE)

    print(f"raw percentiles: {len(pct):,} rows, {pct['country'].nunique()} countries")

    # Filter to target year (defensive — the fetch is single-year already)
    pct = pct[pct["year"] == TARGET_YEAR].copy()
    # PPP factors come from the PRICE-BASE year, not the data year — WID
    # reports incomes in constant LCU of the latest database year (see
    # config.PPP_YEAR).
    ppp = ppp[ppp["year"] == PPP_YEAR]
    assert len(ppp), f"no xlcusp rows for PPP_YEAR={PPP_YEAR} in the raw PPP file"
    pop = pop[pop["year"] == TARGET_YEAR]

    # ------------------------------------------------------------------
    # Validate bin structure: every country must have the full 109 bins
    # covering exactly [0, 1]
    # ------------------------------------------------------------------
    bins_per_country = pct.groupby("country").size()
    assert (bins_per_country == 109).all(), \
        f"countries without 109 bins: {bins_per_country[bins_per_country != 109].to_dict()}"
    width_sum = pct.assign(w=pct["p_high"] - pct["p_low"]).groupby("country")["w"].sum()
    assert (width_sum.round(9) == 1.0).all(), "bin widths do not sum to 1 for some country"

    # ------------------------------------------------------------------
    # Merge PPP factors and population aggregates
    # ------------------------------------------------------------------
    df = (
        pct
        .merge(ppp[["country", "ppp"]], on="country", how="left", validate="many_to_one")
        .merge(pop[["country", "adult_pop", "total_pop"]], on="country",
               how="left", validate="many_to_one")
    )
    # Every fetched country must have PPP and population — fail loudly if not.
    for col in ["ppp", "adult_pop", "total_pop"]:
        missing = df.loc[df[col].isna(), "country"].unique()
        if len(missing):
            print(f"ERROR: missing {col} for: {missing}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # Step 1+2: local currency -> international $, annual -> daily
    # ------------------------------------------------------------------
    df["avg_pretax_per_adult"] = (df["avg_pretax"] / df["ppp"]) / DAYS_PER_YEAR
    df["avg_posttax_per_adult"] = (df["avg_posttax"] / df["ppp"]) / DAYS_PER_YEAR

    # ------------------------------------------------------------------
    # Step 3: per adult -> per capita
    # ------------------------------------------------------------------
    adult_share = df["adult_pop"] / df["total_pop"]
    df["avg_pretax_per_capita"] = df["avg_pretax_per_adult"] * adult_share
    df["avg_posttax_per_capita"] = df["avg_posttax_per_adult"] * adult_share

    # ------------------------------------------------------------------
    # Step 4: bin-specific populations
    # ------------------------------------------------------------------
    bin_width = df["p_high"] - df["p_low"]
    df["bin_adult_pop"] = df["adult_pop"] * bin_width
    df["bin_total_pop"] = df["total_pop"] * bin_width

    # ------------------------------------------------------------------
    # Attach the PIP country name (used as the common country identifier
    # everywhere downstream; the 2-letter WID code is kept as country_code)
    # ------------------------------------------------------------------
    name_map = dict(zip(cmap["country"], cmap["PIP country name"]))
    df["country_name"] = df["country"].map(name_map)
    unmapped = df.loc[df["country_name"].isna(), "country"].unique()
    if len(unmapped):
        print(f"ERROR: fetched countries missing from country_mapping.csv: {unmapped}")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Write output
    # ------------------------------------------------------------------
    out = df.rename(columns={"country": "country_code", "country_name": "country"})[[
        "country", "country_code", "year", "percentile", "p_low", "p_high",
        "avg_pretax_per_adult", "avg_pretax_per_capita", "share_pretax",
        "avg_posttax_per_adult", "avg_posttax_per_capita", "share_posttax",
        "adult_pop", "total_pop", "bin_adult_pop", "bin_total_pop",
    ]].sort_values(["country", "p_low"]).reset_index(drop=True)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(WID_PROCESSED_FILE, index=False)

    n_zero_pre = (out["avg_pretax_per_adult"] == 0).sum()
    n_zero_post = (out["avg_posttax_per_adult"] == 0).sum()
    n_na_post = out["avg_posttax_per_adult"].isna().sum()
    print(f"Saved: {WID_PROCESSED_FILE}")
    print(f"  {len(out):,} rows, {out['country'].nunique()} countries")
    print(f"  zero incomes retained (handled at analysis stage): "
          f"pre-tax {n_zero_pre}, post-tax {n_zero_post}")
    print(f"  missing post-tax values: {n_na_post}")


if __name__ == "__main__":
    main()
