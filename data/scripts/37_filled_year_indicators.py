"""
37_filled_year_indicators.py — inequality indicators at EVERY country-year, from PIP's filled
(lined-up) thousand bins and the deck's adjusted chain, next to WID.

    data/processed/filled_year_indicators.csv

WHAT IT IS
----------
The FILLED counterpart of reference_year_indicators.csv (33_). PIP publishes Gini, shares and
Palma only for the years a country ran a survey. Its lined-up thousand-bins distributions, which
the ETL harmonizes, exist for every year 1990-2024 — interpolated between surveys and extrapolated
beyond them. This table computes every measure from those bins, for PIP as published and the four
adjusted series of the deck's chain (PIP_consinc / PIP_topadj on the WID profile, and the parallel
Wollburg et al. chain), plus WID's two per-capita series at the same years. No reference-year
matching: every country-year is its own row.

ONE ROW PER country x series x year. The columns:

    country, series, year
    kind                 PIP side: "survey" (a PIP survey that year), "interpolated" (a survey
                         both before and after, counting surveys outside 1990-2024 that the
                         basis points to), "extrapolated" (before the first or after the last
                         survey); empty on WID
    survey_year_used     PIP side: the survey the ETL takes the year's welfare concept from
                         (the year itself for a survey year; for an extrapolated year the survey
                         PIP scaled it from)
    distance_to_survey   PIP side: years to the NEAREST survey of the country (any year), 0 in
                         survey years
    welfare_type         PIP side: income or consumption — the ETL's inference for non-survey
                         years, since PIP publishes none
    top1_adjusted        on the two PIP_topadj series only: whether the top-1% append raised the
                         top that year (topadj.py; the gate is per chain, refyears.GATE_BASE)
    wid_extrapolated     on the WID series only: "no" where WID rates the country-year as
                         directly supported by data
    gini, top10_share,   from the bins on the deck's 100-percentile grid (refyears.py): Gini 0-1,
    top1_share, palma,   shares in percent, Palma = top-10% / bottom-40% share, mean $/day
    mean                 (PIP at 2021 prices, WID at 2025 prices — see 33_ on the price bases)

WHAT THE FILLED DATA CAN AND CANNOT TELL YOU — READ THIS BEFORE USING IT
------------------------------------------------------------------------
- The 40 countries with no national PIP survey are NOT here. Their bins are regional placeholder
  distributions: 31 keep exactly the same Gini every year on a handful of shared templates
  (0.346 for 12 countries, 0.493 for 11 Caribbean ones, 0.322 for 4 microstates...), 8 flip
  between two template values, and Argentina (urban-only survey) has no national one. They carry
  no welfare concept either, so the consumption->income step could not be applied.
- EXTRAPOLATED years scale one survey's distribution, so PIP's inequality there is mostly the
  edge survey's, frozen: the Gini equals that survey's exactly in two thirds of them and within
  0.01 in 96% (the script prints the shares per series). They are most country-years at the ends
  of the panel (73% of the countries in 1990, 86% in 2024), so changes measured to or from those
  years are largely mechanical, not observed. The adjusted series do move there, but only through
  the adjustments: the top-1% append takes WID's top-1% share for the year, and the Wollburg
  inverse depends on the income level — neither is a new PIP observation.
- INTERPOLATED years blend the two surveys around them: smooth by construction, with no
  information of their own about year-to-year movement.
- The welfare concept of a non-survey year is inferred by the ETL (harmonized_income_distributions,
  build_welfare_basis); PIP publishes no label for filled years.
- In a filled year the top-1% append imports WID's top-1% share for that year, which in most
  country-years is itself a WID extrapolation (see wid_extrapolated on the WID rows).
- Nothing published to validate filled-year Gini against. The survey years are checked below
  against 33_'s survey-based dataset (identical by construction: same bins, same chain).

PROVENANCE: data/raw/etl/pip_filled_year_indicators (built by 20_cache_from_etl.py with
etl_source.build_chain, because the 1.2M bin rows behind it are too large to commit),
pip_welfare_basis and wid_reference_year_indicators. Runs after 33_ in refresh_from_etl.py.

Run:  python data/scripts/37_filled_year_indicators.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es
import refyears

DATA_DIR = Path(__file__).resolve().parents[1]
OUT_FILE = DATA_DIR / "processed" / "filled_year_indicators.csv"
REFYEAR_FILE = DATA_DIR / "processed" / "reference_year_indicators.csv"

YEARS = range(1990, 2025)
MEASURES = ["gini", "top10_share", "top1_share", "palma", "mean"]
COLUMNS = ["country", "series", "year", "kind", "survey_year_used", "distance_to_survey",
           "welfare_type", "top1_adjusted", "wid_extrapolated"] + MEASURES


def main():
    print("Reading the ETL cache")
    fill = es.load("pip_filled_year_indicators")
    basis = es.load("pip_welfare_basis")
    wid = es.load("wid_reference_year_indicators")
    for t in (fill, basis, wid):
        t["year"] = t["year"].astype(int)
    fill = fill[fill["year"].isin(list(YEARS))]

    # ---- PIP side: classify every country-year against the country's survey years
    kinds = classify(basis)
    pip = fill.merge(kinds, on=["country", "year"], how="left", validate="many_to_one")
    assert pip["kind"].notna().all(), "a filled PIP country-year has no welfare basis"
    assert set(pip["series"]) == set(refyears.PIP_SIDE)
    assert len(pip) == pip["country"].nunique() * len(YEARS) * len(refyears.PIP_SIDE), "the panel has holes"
    pip["top1_adjusted"] = pip["top1_adjusted"].astype(object)
    pip.loc[~pip["series"].isin(refyears.TOPADJ_SERIES), "top1_adjusted"] = np.nan
    pip["wid_extrapolated"] = np.nan

    check_against_survey_dataset(pip)

    # ---- WID side: the same years, every country WID covers
    w = wid[wid["year"].isin(list(YEARS))].copy()
    for c in ("kind", "survey_year_used", "distance_to_survey", "welfare_type", "top1_adjusted"):
        w[c] = np.nan

    out = pd.concat([pip[COLUMNS], w[COLUMNS]], ignore_index=True)
    out = out.sort_values(["series", "country", "year"]).reset_index(drop=True)
    for c in ("survey_year_used", "distance_to_survey"):
        out[c] = out[c].astype("Int64")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_FILE, index=False, float_format="%.10g")
    print(f"\nSaved: {OUT_FILE.relative_to(DATA_DIR.parent)} ({len(out):,} rows, "
          f"{OUT_FILE.stat().st_size / 1024:.0f} KB)")

    summarise(pip, w)


def classify(basis):
    """kind / survey_year_used / distance_to_survey / welfare_type for every labelled country-year."""
    b = basis[["country", "year", "welfare_type", "survey_year_used"]].copy()
    b["survey_year_used"] = b["survey_year_used"].astype(int)
    surveys = refyears.survey_years(basis)
    inside = surveys.groupby("country")["year"].apply(lambda s: set(s.astype(int)))
    # Surveys outside 1990-2024 (Algeria 1988, say) exist only as a survey_year_used the basis
    # points to; they still bracket a year, so they count for interpolated vs extrapolated.
    outside = b.loc[~b["survey_year_used"].between(min(YEARS), max(YEARS))].groupby("country")["survey_year_used"].apply(set)
    by_country = {c: np.sort(np.array(sorted(inside.get(c, set()) | outside.get(c, set())), dtype=int))
                  for c in b["country"].unique()}
    kind, dist = [], []
    for c, y in zip(b["country"], b["year"]):
        s = by_country[c]
        dist.append(int(np.abs(s - y).min()))
        kind.append("survey" if y in inside.get(c, set()) else "interpolated" if s[0] < y < s[-1] else "extrapolated")
    b["kind"], b["distance_to_survey"] = kind, dist
    assert ((b["kind"] == "survey") == (b["year"] == b["survey_year_used"])).all(), \
        "survey years disagree between the welfare basis and refyears.survey_years"
    return b


def check_against_survey_dataset(pip):
    """At every survey country-year the filled measures must equal 33_'s (same bins, same chain)."""
    ref = pd.read_csv(REFYEAR_FILE, keep_default_na=False, na_values=[""])
    ref = ref[ref["series"].isin(refyears.PIP_SIDE) & (ref["distance"] == 0)]
    ref = ref.drop_duplicates(["series", "country", "year"])
    j = pip[pip["kind"] == "survey"].merge(ref, on=["series", "country", "year"], suffixes=("", "_ref"))
    n_survey = int((pip["kind"] == "survey").sum())
    assert len(j) == n_survey, f"only {len(j)} of {n_survey} survey rows found in {REFYEAR_FILE.name}"
    for m in MEASURES:
        assert np.allclose(j[m], j[f"{m}_ref"], rtol=1e-8, atol=1e-10), \
            f"{m} differs from the survey-based dataset at survey years — rebuild the cache"
    topadj = j["series"].isin(refyears.TOPADJ_SERIES)
    assert (j.loc[topadj, "top1_adjusted"].astype(bool) == j.loc[topadj, "top1_adjusted_ref"].astype(bool)).all(), \
        "the top-1% gate differs from the survey-based dataset at survey years"
    print(f"  survey years match {REFYEAR_FILE.name}: {len(j):,} rows x {len(MEASURES)} measures")


def summarise(pip, wid):
    p = pip[pip["series"] == "PIP"]
    print(f"\nPIP side: {p['country'].nunique()} countries x {len(YEARS)} years")
    mix = p.groupby("year")["kind"].value_counts(normalize=True).unstack().fillna(0)
    show = [1990, 1995, 2000, 2005, 2010, 2015, 2019, 2022, 2023, 2024]
    print("  share of countries by kind:")
    print((mix.loc[show, ["survey", "interpolated", "extrapolated"]] * 100).round(0).astype(int).to_string())
    print("  country-years:", p["kind"].value_counts().to_dict())

    # How much of the extrapolated data is the edge survey's distribution, frozen?
    first = p[p["kind"] == "survey"].groupby("country")["year"].min()
    last = p[p["kind"] == "survey"].groupby("country")["year"].max()
    for series in refyears.PIP_SIDE:
        e = pip[(pip["series"] == series) & (pip["kind"] == "extrapolated")]
        ss = pip[(pip["series"] == series) & (pip["kind"] == "survey")].set_index(["country", "year"])["gini"]
        edge = np.where(e["year"] < e["country"].map(first), e["country"].map(first), e["country"].map(last))
        g_edge = np.array([ss[(c, int(y))] for c, y in zip(e["country"], edge)])
        diff = np.abs(e["gini"].to_numpy() - g_edge)
        print(f"  {series:<16} extrapolated years at the edge survey's Gini: exactly {np.mean(diff < 1e-6):.0%}, "
              f"within 0.01 {np.mean(diff < 0.01):.0%} (of {len(e):,})")
    print(f"WID side: {wid['country'].nunique()} countries every year")


if __name__ == "__main__":
    main()
