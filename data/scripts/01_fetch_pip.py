"""
01_fetch_pip.py — download PIP percentile data and cache the 2023 extract.

WHAT THIS FETCHES
-----------------
The World Bank PIP (Poverty and Inequality Platform) "thousand bins"
distribution, as republished in the Our World in Data catalog:

    {PIP_URL}

For each country-year it contains 1000 income bins, each holding exactly 0.1%
of the population, with:

    quantile : 1..1000 (bin rank, 1 = poorest 0.1%)
    avg      : mean income within the bin — DAILY, PER CAPITA,
               2021 PPP international dollars
    pop      : number of people in the bin (persons)
    region   : World Bank PIP region name (kept as a convenience lookup)

Income concept: disposable household income or consumption (whichever the
underlying survey measures), divided by TOTAL population (adults + children).
This "per capita" basis is a key difference from WID's "per adult" basis —
the per-adult/per-capita adjustment happens on the WID side (02_process_wid.py).

WHAT THIS SCRIPT DOES
---------------------
1. Downloads the full feather file (~28 MB, all years 1990-2025).
2. Filters to TARGET_YEAR (2023).
3. Runs basic validation (1000 bins per country, no missing/negative values).
4. Writes the extract to data/raw/pip/ as a compressed CSV (committed to the
   repo, ~few MB), so downstream steps don't depend on the network.

Run:  python data/scripts/01_fetch_pip.py
"""

import sys
import pandas as pd

from config import PIP_URL, PIP_RAW_FILE, RAW_PIP_DIR, TARGET_YEAR


def main():
    print(f"Downloading PIP thousand-bins data from:\n  {PIP_URL}")
    df = pd.read_feather(PIP_URL)
    print(f"  full file: {len(df):,} rows, years {df['year'].min()}-{df['year'].max()}")

    # ------------------------------------------------------------------
    # Filter to the target year
    # ------------------------------------------------------------------
    df = df[df["year"] == TARGET_YEAR].copy()
    # Cast categories/extension dtypes to plain types for a clean CSV
    df["country"] = df["country"].astype(str)
    df["region"] = df["region"].astype(str)
    df = df[["country", "year", "region", "quantile", "avg", "pop"]]
    print(f"  {TARGET_YEAR} extract: {len(df):,} rows, {df['country'].nunique()} countries")

    # ------------------------------------------------------------------
    # Validation — fail loudly rather than write a bad cache
    # ------------------------------------------------------------------
    problems = []
    bins_per_country = df.groupby("country").size()
    if not (bins_per_country == 1000).all():
        problems.append(f"countries without exactly 1000 bins: "
                        f"{bins_per_country[bins_per_country != 1000].to_dict()}")
    if df["avg"].isna().any():
        problems.append(f"{df['avg'].isna().sum()} missing avg values")
    if (df["avg"] < 0).any():
        problems.append(f"{(df['avg'] < 0).sum()} negative avg values")
    if df["pop"].isna().any() or (df["pop"] <= 0).any():
        problems.append("missing or non-positive pop values")

    if problems:
        print("VALIDATION FAILED:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print("  validation: 1000 bins/country, no missing/negative values ✓")

    # ------------------------------------------------------------------
    # Write the cache
    # ------------------------------------------------------------------
    RAW_PIP_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PIP_RAW_FILE, index=False, compression="gzip")
    print(f"Saved: {PIP_RAW_FILE} ({PIP_RAW_FILE.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
