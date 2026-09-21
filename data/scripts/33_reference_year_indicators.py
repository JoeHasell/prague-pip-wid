"""
33_reference_year_indicators.py — inequality indicators at reference years, from the
deck's ADJUSTED PIP bins.

    data/processed/reference_year_indicators.csv

WHAT IT IS
----------
The ETL's `inequality_comparison` compares PIP's published, survey-year measures
with WID's at matched reference years. This is the same kind of table, but the
PIP side comes from the harmonized bins — PIP as published, PIP on an income
basis (PIP_consinc) and PIP with WID's top 1% appended (PIP_topadj), i.e. the
deck's own chain (etl_source.load_bins) — and every reference year 1990-2024 is
matched on its own. For each country, series and reference year it records the
survey year actually used (`year`), how far away it was (`distance`), the
welfare concept of that survey, and Gini, top-10% / bottom-40% / top-1% shares,
Palma, mean and population computed from the bins by refyears.py.

The WID side is the deck's two per-capita series at the reference year itself
(WID has every year; `distance` is 0), from the same indicator code on the same
100-percentile grid, so the two sides are directly comparable.

PROVENANCE — READ THIS BEFORE USING THE FILE
-------------------------------------------
- This file lives in data/processed/ next to the local Stata pipeline's outputs
  but is NOT one of them: it is built from the ETL cache in data/raw/etl/
  (reference_year_bins, wid_reference_year_indicators, pip_welfare_basis), by
  this script, on every `refresh_from_etl.py`. legacy_guard.py's rule — the
  1N_ scripts read processed/, the 2N_/3N_ scripts read raw/etl/ — still holds.
- PIP survey years are `pip_welfare_basis.survey_year_used == year`. The 40 of
  211 harmonized countries with no PIP survey at all have no rows on the PIP side.
- `mean` mixes price bases: PIP at 2021 prices, WID at 2025 prices (both 2021
  PPPs) — WID levels sit ~17% above a like-for-like comparison. Everything
  relative (Gini, shares, Palma) is unaffected. See etl_source.py.
- `population` is each series' OWN bin population: PIP's own counts on the PIP
  side, the ETL's yardstick (OWID population) on the WID side. They differ by
  more than 1% for 38 countries (see etl_mld.py). Weight cross-country averages
  by one of them, not both.
- `top1_adjusted` is False for the countries the top-1% gate left alone (their
  survey already shows a larger top-1% share than WID; see topadj.py) — there
  PIP_topadj equals PIP_consinc. The gate is decided per chain (GATE_BASE).
- `PIP_consinc_wb` / `PIP_topadj_wb` are a PARALLEL comparison chain: consumption
  countries put on PIP's own disposable-income basis by inverting Wollburg,
  Hallegatte & Mahler (2023)'s income->consumption fit (consinc.py, "A SECOND
  METHOD"), floored at $0.28/day, then the same top-1% append. The deck's
  baseline is still the WID profile; these two exist only here and on the
  year-vs-year scatters (34_).
- One survey serves up to eleven reference years. For a comparison between two
  reference years use refyears.pair(), which enforces the ETL's same-welfare rule
  and refuses to compare a survey with itself. The ETL's own 1993/2019 table
  RE-MATCHES a country to a same-welfare pair further away where this drops it:
  pair(1993, 2019) keeps 94 PIP countries against the ETL's 97 (Argentina and
  Uruguay have no national survey; Belarus, Belize, Kazakhstan, Nicaragua, Peru,
  Romania and Saint Lucia are the ETL's re-matches), and adds six the ETL's
  consolidated published series lacks (Burundi, Central African Republic, India,
  Madagascar, Nepal, Syria).
- The bins are a lined-up distribution, not the survey microdata. Against PIP's
  published survey-year Gini the `PIP` rows sit a median 0.0006 lower; 21 of
  2,200 survey country-years are more than 0.01 away (Malawi 1997 −0.063 the
  worst), and top-1% shares are within 1pp for 99.4% of them. Measured 2026-09-21.

Run:  python data/scripts/33_reference_year_indicators.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es
import refyears
import topadj

OUT_FILE = Path(__file__).resolve().parents[1] / "processed" / "reference_year_indicators.csv"

# THE MATCHING CONFIGURATION. Every year the harmonized panel covers, the ETL's
# +-5 window, ties to the earlier survey (see refyears.py for why), and no
# excluded years: the ETL excludes 1988-89 and 2020-24 to protect one specific
# 1993/2019 comparison, which is a decision for the reader of a pair, not for a
# table of every year. Change these here and nowhere else.
REFERENCE_YEARS = range(1990, 2025)
MAXIMUM_DISTANCE = 5
TIE_BREAK_STRATEGY = "lower"
EXCLUDED_YEARS = ()

COLUMNS = ["country", "series", "ref_year", "year", "distance", "tie", "welfare_type", "adjusted",
           "top1_adjusted", "wid_extrapolated", "n_bins"] + refyears.INDICATORS

# The top-1% gate is decided per CHAIN, on the income-basis series the append is
# built on (topadj.top1_shares): the baseline chain on PIP_consinc, the Wollburg
# et al. chain on PIP_consinc_wb. `top1_adjusted` therefore differs between the
# two chains for the same country-year.
GATE_BASE = {
    "PIP": "PIP_consinc", "PIP_consinc": "PIP_consinc", "PIP_topadj": "PIP_consinc",
    "PIP_consinc_wb": "PIP_consinc_wb", "PIP_topadj_wb": "PIP_consinc_wb",
}
assert set(GATE_BASE) == set(refyears.PIP_SIDE), "every PIP-side series needs a gate base"


def main():
    print("Reading the ETL cache")
    bins = es.load_bins("reference_year_bins")
    basis = es.load("pip_welfare_basis")
    surveys = refyears.survey_years(basis)
    have = set(zip(bins.loc[bins["series"] == "PIP", "country"], bins.loc[bins["series"] == "PIP", "year"]))
    want = set(zip(surveys["country"], surveys["year"]))
    assert have == want, (f"reference_year_bins covers {len(have)} PIP country-years, the welfare basis "
                          f"lists {len(want)} survey years — refresh the cache")
    print(f"  {len(surveys):,} PIP survey country-years, {surveys['country'].nunique()} countries, "
          f"{surveys['year'].min()}-{surveys['year'].max()}")

    # ---- PIP side: indicators at every survey year, then matched to reference years
    ind = refyears.indicators_from_bins(bins[bins["series"].isin(refyears.PIP_SIDE)])
    gate = []
    for y, gy in bins.groupby("year", observed=True):
        for base in sorted(set(GATE_BASE.values())):
            g8 = topadj.top1_shares(gy, base)
            for s in [s for s, b in GATE_BASE.items() if b == base]:
                gate.append(pd.DataFrame({"country": g8.index, "year": int(y), "series": s,
                                          "top1_adjusted": g8["adjust"].to_numpy()}))
    gate = pd.concat(gate, ignore_index=True)

    matches = refyears.match_reference_years(surveys, REFERENCE_YEARS, maximum_distance=MAXIMUM_DISTANCE,
                                             tie_break_strategy=TIE_BREAK_STRATEGY,
                                             excluded_years=EXCLUDED_YEARS)
    pip = (matches.merge(ind, on=["country", "year"], how="inner")
                  .merge(surveys, on=["country", "year"], how="left")
                  .merge(gate, on=["country", "year", "series"], how="left"))
    assert pip["welfare_type"].notna().all() and pip["top1_adjusted"].notna().all()
    assert len(pip) == len(matches) * len(refyears.PIP_SIDE), "a matched survey year lost a series"
    pip["wid_extrapolated"] = np.nan

    # ---- WID side: the reference year itself, from the cache-time indicator table
    wid = es.load("wid_reference_year_indicators")
    wid["year"] = wid["year"].astype(int)
    # The cache-time computation must be reproducible from the committed bins:
    # recompute WID post-tax at the survey country-years and demand equality.
    check = refyears.indicators_from_bins(bins[bins["series"] == "WID_posttax_per_capita"])
    j = check.merge(wid, on=["series", "country", "year"], suffixes=("", "_cache"))
    assert len(j) == len(check), "cache-time WID table is missing survey country-years"
    for c in refyears.INDICATORS:
        assert np.allclose(j[c], j[f"{c}_cache"], rtol=1e-9, atol=1e-12), \
            f"wid_reference_year_indicators no longer matches the bins on {c} — refresh the cache"
    print(f"  WID cache-time indicators reproduced from the bins at {len(j):,} country-years")

    wid["ref_year"] = wid["year"]
    wid["distance"] = 0
    wid["tie"] = False
    for c in ("welfare_type", "adjusted", "top1_adjusted"):
        wid[c] = np.nan
    wid = wid[wid["ref_year"].isin(list(REFERENCE_YEARS))]

    out = pd.concat([pip[COLUMNS], wid[COLUMNS]], ignore_index=True)
    out = out.sort_values(["series", "country", "ref_year"]).reset_index(drop=True)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_FILE, index=False, float_format="%.10g")
    print(f"\nSaved: {OUT_FILE.relative_to(OUT_FILE.parents[2])} ({len(out):,} rows, {OUT_FILE.stat().st_size / 1024:.0f} KB)")

    # ---- summary
    print(f"\nMatching: window +-{MAXIMUM_DISTANCE}, ties -> {TIE_BREAK_STRATEGY}, "
          f"excluded survey years: {list(EXCLUDED_YEARS) or 'none'}")
    p = out[out["series"] == "PIP"]
    per_year = p.groupby("ref_year")["country"].nunique()
    print("  PIP countries matched per reference year:")
    print("   " + "  ".join(f"{y}:{n}" for y, n in per_year.items()))
    print("  distance of the survey used: " +
          ", ".join(f"{d} yr: {n}" for d, n in p["distance"].value_counts().sort_index().items()))
    print(f"  ties broken: {int(p['tie'].sum())} country-reference-years")
    print(f"  top-1% gate left {int((~p['top1_adjusted'].astype(bool)).sum())} PIP country-reference-years unadjusted"
          f" (Wollburg chain: {int((~out.loc[out['series'] == 'PIP_topadj_wb', 'top1_adjusted'].astype(bool)).sum())})")
    w = out[out["series"] == "WID_posttax_per_capita"]
    print(f"  WID: {w['country'].nunique()} countries every year; "
          f"{int((w['wid_extrapolated'] == 'no').sum())} country-years rated as directly data-backed")


if __name__ == "__main__":
    main()
