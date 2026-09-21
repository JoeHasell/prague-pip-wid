"""
refyears.py — inequality indicators from bins, and the reference-year matcher.

Two things the reference-year dataset (33_reference_year_indicators.py) needs,
kept together so the PIP side and the WID side cannot drift apart:

  1. indicators_from_bins()   Gini, top-10% / bottom-40% / top-1% shares, Palma,
                              mean and population for every (series, country,
                              year) in a bins frame — on ANY grid, including the
                              ragged, re-ranked PIP_topadj (see etl_source.TOPADJ_METHOD).
  2. match_reference_years()  each country's nearest survey year to each
                              reference year — the inequality_comparison method
                              from OWID's ETL, applied to every reference year
                              INDEPENDENTLY rather than to one 1993/2019 pair.
     pair()                   forms a comparison between two reference years
                              afterwards, applying the ETL's same-welfare rule.

THE METHOD BEING PORTED
-----------------------
etl/steps/data/garden/poverty_inequality/2025-01-22/inequality_comparison.py
(`match_ref_years`, REFERENCE_YEARS) matches PIP's PUBLISHED survey-year
measures to two reference years at once: a window of `maximum_distance` years
around each, `excluded_years` removed from the candidates, the nearest survey
wins, and an exact tie (two surveys equidistant on either side) is broken by
`tie_break_strategy` — "lower" takes the earlier year, "higher" the later. The
two windows are then PAIRED: a country needs a survey in both, and where the
nearest surveys differ in welfare concept the ETL re-matches to a same-welfare
pair further away (Bolivia 1992 -> 1997 against 2019, Kazakhstan 1993 -> 1996).

Here each reference year is matched on its own, so there is nothing to pair at
match time. What is kept: the window, the exclusions, the distance, nearest
wins, the tie-break. What is dropped: the outer merge of two windows, the
welfare / reporting-level pair scoring, `min_interval`, `only_all_series` and
the wide reshape. The welfare rule moves to pair(): a PIP comparison between two
reference years keeps only same-welfare pairs — and DROPS the country where the
ETL would have re-matched, because there is no second-nearest survey to fall
back on once each year is matched alone. Measured against the ETL's own 1993 /
2019 output this port reproduces the matched years for 95 of 97 countries at
1993 and 97 of 97 at 2019; the two are exactly those re-matches.

Reporting level does not exist here: the harmonized bins are national-only, and
a country PIP surveys only in urban areas (Argentina) has no survey year at all.

TIE-BREAK DEFAULT. The ETL uses "lower" at 1993 and "higher" at 2019 to make the
pair as WIDE as possible. With no pair there is nothing to widen, so the default
is "lower" everywhere — the rule 26_fig_reference_year_observed.py already
applies, and the one the ETL's own welfare-basis decision tree uses ("ties
resolve to the earlier survey because that is where PIP puts them"). Per-year
overrides accept the ETL's REFERENCE_YEARS dict verbatim (ETL_1993_2019 below),
so its exact matching can be reproduced for a check.

ONE SURVEY SERVES MANY REFERENCE YEARS. With a +-5 window, a country with a
single 2017 survey is the match for every reference year 2012-2022. Consecutive
reference years are therefore NOT independent samples, and a comparison of two
reference years can compare a survey with itself — pair(min_interval=1) refuses
that by default. Read `distance` (and `tie`) before trusting a single year.

THE FLOAT32 RANK TRAP. The ETL stores p_low / p_high as float32, so p90p91
arrives as 0.8999999761581421 and a test `p_low >= 0.9 - 1e-9` silently drops
the whole p90 bin (US 2023 top-10% share 28.5 instead of 30.5). Every share
here is a rank-WINDOW integral over [lo, hi] — the pattern of
21_fig_bridging_from_etl.rank_window — never a threshold or label lookup, and
the one tolerance that remains (RANK_EPS, for the bin-width identity) is well
above float32 noise. Within-bin population is taken as uniform, which is all the
bin data supports; a window edge at 0.4 or 0.9 splits a bin pro rata.
"""

import numpy as np
import pandas as pd

# Well above float32 rounding (~6e-8 at these magnitudes), well below the
# narrowest bin width (0.001 on the ETL's own grid).
RANK_EPS = 1e-6

# The deck's PIP-side chain (etl_source.load_bins) and the two WID per-capita
# series the dataset carries. Per-adult WID gives the same Gini and shares by
# construction (a per-capita conversion is a uniform rescale); only `mean` and
# `population` would differ.
PIP_SIDE = ("PIP", "PIP_consinc", "PIP_topadj")
WID_SIDE = ("WID_pretax_per_capita", "WID_posttax_per_capita")

# Shares are in PERCENT, as PIP and WID publish them.
INDICATORS = ["gini", "top10_share", "bottom40_share", "top1_share", "palma", "mean", "population"]

# The ETL's own configuration, copied verbatim from
# etl/steps/data/garden/poverty_inequality/2025-01-22/inequality_comparison.py
# (REFERENCE_YEARS). `min_interval` is a PAIR property and is ignored by the
# matcher; pair() carries it. Pass as `overrides=` to reproduce the ETL's years.
ETL_1993_2019 = {
    1993: {"maximum_distance": 5, "tie_break_strategy": "lower", "min_interval": 0,
           "excluded_years": [1988, 1989]},
    2019: {"maximum_distance": 5, "tie_break_strategy": "higher", "min_interval": 0,
           "excluded_years": [2020, 2021, 2022, 2023, 2024]},
}

GROUP = ["series", "country", "year"]


# ---------------------------------------------------------------------------
# 1. Indicators from bins
# ---------------------------------------------------------------------------
def window_income(p_low, p_high, avg, pop, lo, hi):
    """Total income of the population between ranks lo and hi.

    Each bin's population is spread uniformly across its own rank width, so a bin
    straddling an edge contributes pro rata. Works on any grid — 100 bins, the
    ETL's 109, or the re-ranked append series — because it never asks what a bin
    is called, only where it sits.
    """
    p_low = np.asarray(p_low, dtype=float)
    p_high = np.asarray(p_high, dtype=float)
    width = p_high - p_low
    overlap = np.clip(np.minimum(p_high, hi) - np.maximum(p_low, lo), 0.0, None)
    return float((np.asarray(avg, dtype=float) * np.asarray(pop, dtype=float) * overlap / width).sum())


def gini_from_bins(avg, pop):
    """Gini via the Lorenz curve, trapezoid rule, valid for unequal bin widths.

    Ported from the ETL (inequality_trends_by_reference_year.compute_metrics),
    per group rather than on a fixed-width matrix so a ragged frame works. The
    Lorenz curve is traced in INCOME order (stable sort, so a monotone
    distribution is unchanged), because an adjusted series can be non-monotone
    along the rank axis. Bins carry no within-bin inequality, so this is a slight
    underestimate — the same one for every series.
    """
    x = np.asarray(avg, dtype=float)
    w = np.asarray(pop, dtype=float)
    w = w / w.sum()
    order = np.argsort(x, kind="stable")
    x, w = x[order], w[order]
    income = w * x
    lorenz = np.cumsum(income) / income.sum()
    lorenz_prev = np.concatenate([[0.0], lorenz[:-1]])
    return float(1.0 - ((lorenz + lorenz_prev) * w).sum())


def indicators_from_bins(bins):
    """One row per (series, country, year): INDICATORS plus `n_bins`.

    Asserts what the bin data must satisfy for the integrals to mean anything:
    widths summing to one, positive population, no missing income. Palma is NaN
    where the bottom 40% has no income at all (it cannot happen on these series,
    but a division by zero must not pass silently).
    """
    need = set(GROUP + ["p_low", "p_high", "avg", "pop"])
    missing = sorted(need - set(bins.columns))
    assert not missing, f"bins frame lacks {missing}"
    assert bins["avg"].notna().all(), "missing bin incomes"
    assert (bins["pop"].to_numpy(dtype=float) > 0).all(), "non-positive bin populations"

    rows = []
    for (series, country, year), g in bins.groupby(GROUP, observed=True, sort=True):
        p_low = g["p_low"].to_numpy(dtype=float)
        p_high = g["p_high"].to_numpy(dtype=float)
        assert abs((p_high - p_low).sum() - 1.0) < RANK_EPS, \
            f"{series} {country} {year}: bin widths sum to {(p_high - p_low).sum():.8f}, not 1"
        avg = g["avg"].to_numpy(dtype=float)
        pop = g["pop"].to_numpy(dtype=float)
        total = float((avg * pop).sum())
        top10 = 100.0 * window_income(p_low, p_high, avg, pop, 0.90, 1.00) / total
        bottom40 = 100.0 * window_income(p_low, p_high, avg, pop, 0.00, 0.40) / total
        top1 = 100.0 * window_income(p_low, p_high, avg, pop, 0.99, 1.00) / total
        rows.append({
            "series": series, "country": country, "year": int(year), "n_bins": len(g),
            "gini": gini_from_bins(avg, pop),
            "top10_share": top10,
            "bottom40_share": bottom40,
            "top1_share": top1,
            "palma": top10 / bottom40 if bottom40 > 0 else np.nan,
            "mean": total / float(pop.sum()),
            "population": float(pop.sum()),
        })
    return pd.DataFrame(rows, columns=GROUP + ["n_bins"] + INDICATORS)


# ---------------------------------------------------------------------------
# 2. Reference years
# ---------------------------------------------------------------------------
def survey_years(basis):
    """The PIP country-years that ARE surveys, from the ETL's pip_welfare_basis.

    A year is a survey year when the concept it carries comes from a survey taken
    that same year (`survey_year_used == year`); every other year in the lined-up
    panel borrows a neighbouring survey's concept. Countries with no survey at all
    have no basis rows and so never appear here.
    """
    s = basis[basis["survey_year_used"].astype(int) == basis["year"].astype(int)]
    s = s[["country", "year", "welfare_type", "adjusted"]].copy()
    s["year"] = s["year"].astype(int)
    assert not s.duplicated(["country", "year"]).any(), "duplicate survey country-years"
    return s.sort_values(["country", "year"]).reset_index(drop=True)


def match_reference_years(surveys, reference_years, maximum_distance=5,
                          tie_break_strategy="lower", excluded_years=(), overrides=None):
    """Each country's nearest survey year to each reference year, matched independently.

    surveys           one row per (country, year) — a table of years that may be
                      matched; other columns are ignored (merge them back on
                      (country, year) afterwards).
    reference_years   iterable of years to match.
    maximum_distance  the window: a survey can be at most this many years away.
    tie_break_strategy "lower" (earlier survey) or "higher" (later), applied only
                      when two surveys are equidistant on opposite sides.
    excluded_years    SURVEY years never used as a match, for every reference year.
    overrides         {ref_year: {...}} — per-reference-year values for the three
                      settings above (the ETL's REFERENCE_YEARS dict works as is;
                      its `min_interval` is ignored here, see pair()).

    Returns country, ref_year, year, distance, tie — one row per country and
    reference year that has a match; reference years with no survey in their
    window simply have no rows.
    """
    assert not surveys.duplicated(["country", "year"]).any(), "surveys must be one row per country-year"
    overrides = overrides or {}
    base = surveys[["country", "year"]].copy()
    base["year"] = base["year"].astype(int)

    out = []
    for y in reference_years:
        y = int(y)
        cfg = {"maximum_distance": maximum_distance, "tie_break_strategy": tie_break_strategy,
               "excluded_years": list(excluded_years)}
        cfg.update({k: v for k, v in overrides.get(y, {}).items() if k in cfg})
        assert cfg["tie_break_strategy"] in ("lower", "higher"), cfg["tie_break_strategy"]

        d = base[(base["year"] >= y - cfg["maximum_distance"]) & (base["year"] <= y + cfg["maximum_distance"])]
        d = d[~d["year"].isin(cfg["excluded_years"])].copy()
        if d.empty:
            continue
        d["distance"] = (d["year"] - y).abs()
        # Nearest wins; an exact tie is two surveys on opposite sides of the
        # reference year, and the strategy says which side.
        d["_side"] = d["year"] if cfg["tie_break_strategy"] == "lower" else -d["year"]
        d = d.sort_values(["country", "distance", "_side"], kind="stable")
        nearest = d.groupby("country")["distance"].transform("min")
        tied = d[d["distance"] == nearest].groupby("country")["year"].nunique().gt(1)
        first = d.drop_duplicates("country", keep="first").copy()
        first["tie"] = first["country"].map(tied).astype(bool)
        first["ref_year"] = y
        out.append(first[["country", "ref_year", "year", "distance", "tie"]])

    if not out:
        return pd.DataFrame(columns=["country", "ref_year", "year", "distance", "tie"])
    res = pd.concat(out, ignore_index=True)
    res["year"] = res["year"].astype(int)
    res["distance"] = res["distance"].astype(int)
    return res.sort_values(["country", "ref_year"]).reset_index(drop=True)


def pair(tb, ref_a, ref_b, same_welfare=True, min_interval=1):
    """A comparison between two reference years of the long indicators table.

    Merges the rows at `ref_a` and `ref_b` on (country, series) into one wide row
    per pair, with `_a` / `_b` suffixes and a `change_<indicator>` column for each
    indicator present. Then applies the ETL's two pair rules:

      same_welfare   where BOTH rows carry a welfare type (the PIP side), keep the
                     pair only if it is the same one. Rows without a welfare type
                     (WID) always pass. Unlike the ETL this cannot re-match to a
                     same-welfare survey further away; the country is dropped.
      min_interval   drop pairs whose matched SURVEY years are closer than this
                     — at the default 1, a survey is never compared with itself.
    """
    a = tb[tb["ref_year"] == ref_a].drop(columns="ref_year")
    b = tb[tb["ref_year"] == ref_b].drop(columns="ref_year")
    m = a.merge(b, on=["country", "series"], suffixes=("_a", "_b"))
    if same_welfare and "welfare_type_a" in m.columns:
        both = m["welfare_type_a"].notna() & m["welfare_type_b"].notna()
        m = m[~both | (m["welfare_type_a"] == m["welfare_type_b"])]
    m = m[(m["year_b"] - m["year_a"]).abs() >= min_interval].copy()
    for ind in INDICATORS:
        if f"{ind}_a" in m.columns:
            m[f"change_{ind}"] = m[f"{ind}_b"] - m[f"{ind}_a"]
    m.insert(2, "ref_year_b", ref_b)
    m.insert(2, "ref_year_a", ref_a)
    return m.sort_values(["series", "country"]).reset_index(drop=True)
