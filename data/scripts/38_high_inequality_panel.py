"""
38_high_inequality_panel.py — how many countries have high inequality, year by year: the World
Bank's "number of countries with high inequality" (Figure 2 of its June 2024 blog) on the deck's
series, with high = at least as unequal as the United States in 2022.

    data/processed/high_inequality_panel.csv   the country-level panel
    data/figures/fig_high_inequality.json       <- high-inequality-count
                                                   (components/fig-high-inequality.js)

WHAT IT IS
----------
For every year 1990-2024 and the 171 countries with a national PIP survey, each series' Gini,
top-10% share, top-1% share and Palma ratio:

    PIP side   (PIP as published, on an income basis, with WID's top 1% appended) from each
               country's NEAREST SURVEY at any distance, either side of the year (ties to the
               earlier survey) — the deck's survey-based rule without the +-5 cap. `distance` is
               the gap to that survey; `old` = distance > 5 years (the Figma's "low opacity").
    WID side   (post-tax and pre-tax national income per capita) at the year itself; never old.

A country counts as HIGH-INEQUALITY in a year when its value is at least the United States' value
in 2022 in the same series and measure (printed below; PIP's US 2022 Gini is 0.41, next to the
World Bank's own 0.40 line). The component also shows the change view: rising / stable / falling
between a base year and each year, stable being within +-2 Gini points or +-5% for the others.

WHY TWO-SIDED MATCHING, NOT "THE MOST RECENT SURVEY AT THE TIME"
----------------------------------------------------------------
The blog describes each column as "using the most recent household survey at the time" and
calls data old when the survey is more than five years back. Taken literally (surveys up to the
year only) that gives 59 high-inequality countries in 2000 on PIP's published Gini > 40, against
the blog's 77; the nearest survey on EITHER side gives 79, and PIP's lined-up data 75. The
two-sided rule is the one that reproduces the Bank's own numbers, and it is the deck's rule, so
it is used here. The script prints the cross-check.

WHAT THIS CANNOT DO — READ BEFORE USING
---------------------------------------
- Counts cannot match the blog exactly: it used PIP's 2024 vintage, this is the 2026-06 one.
- With no distance cap the nearest survey can be decades away; "old" dominates the early 1990s
  and the last years.
- The threshold is the US in 2022 IN EACH SERIES: comparable within a series, not across them;
  PIP as published still compares consumption countries with US income.
- A change between two years that rest on the same survey is zero by construction (the component
  counts it as stable and says so), and PIP as published can switch welfare concept in between.
- WID has an estimate every year, so its bars carry no old/recent split, although most recent WID
  country-years are WID's own extrapolations.
- The 40 countries without a national survey are left out, as in 37_.

INPUTS: data/processed/filled_year_indicators.csv (37_; its survey rows carry every PIP series,
the WID rows every year), the WID per-capita population yardstick, PIP's seven regions.

Run:  python data/scripts/38_high_inequality_panel.py   (after 37_; refresh_from_etl.py runs it)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es
import refyears

DATA_DIR = Path(__file__).resolve().parents[1]
IN_FILE = DATA_DIR / "processed" / "filled_year_indicators.csv"
OUT_FILE = DATA_DIR / "processed" / "high_inequality_panel.csv"
FIG_FILE = DATA_DIR / "figures" / "fig_high_inequality.json"

YEARS = list(range(1990, 2025))
THRESHOLD_COUNTRY, THRESHOLD_YEAR = "United States", 2022
OLD_AFTER = 5                      # years to the nearest survey beyond which data counts as old
MAX_DISTANCE = 99                  # no cap: every country is matched to its nearest survey
POP_SERIES = "WID_pretax_per_capita"
# The five series of the Figma strip, in its order, with its labels.
SERIES = {
    "PIP": "PIP original",
    "PIP_consinc": "PIP cons→inc",
    "PIP_topadj": "PIP top adj",
    "WID_posttax_per_capita": "WID",
    "WID_pretax_per_capita": "WID original",
}
PIP_SERIES = [s for s in SERIES if s.startswith("PIP")]
MEASURES = {"gini": ("Gini", 4), "top10_share": ("Top 10% share", 2),
            "top1_share": ("Top 1% share", 2), "palma": ("Palma ratio", 3)}
# The change view's stable band: absolute for the Gini, relative for the rest.
STABLE = {"gini": ("abs", 0.02), "top10_share": ("rel", 0.05), "top1_share": ("rel", 0.05),
          "palma": ("rel", 0.05)}
# The World Bank blog's own figures, for the cross-check.
WB_BLOG = {2000: 77, 2022: 52}
COLUMNS = ["country", "region", "series", "year", "survey_year", "distance", "old"] + list(MEASURES) + ["population"]


def main():
    fd = pd.read_csv(IN_FILE, keep_default_na=False, na_values=[""])
    fd["year"] = fd["year"].astype(int)

    # ---- PIP side: nearest survey at any distance, per year
    surv = fd[(fd["series"] == "PIP") & (fd["kind"] == "survey")][["country", "year"]]
    countries = sorted(surv["country"].unique())
    m = refyears.match_reference_years(surv, YEARS, maximum_distance=MAX_DISTANCE, tie_break_strategy="lower")
    assert len(m) == len(countries) * len(YEARS), "a country-year found no survey"
    vals = fd[fd["series"].isin(PIP_SERIES) & (fd["kind"] == "survey")][["country", "series", "year"] + list(MEASURES)]
    pip = (m.merge(vals, on=["country", "year"], how="left")
             .rename(columns={"year": "survey_year", "ref_year": "year"}))
    assert pip[list(MEASURES)].notna().all().all(), "a matched survey lacks a measure"
    pip["old"] = pip["distance"] > OLD_AFTER

    # ---- WID side: the year itself, on the same countries
    wid = fd[fd["series"].isin([s for s in SERIES if s.startswith("WID")]) & fd["country"].isin(countries)
             & fd["year"].isin(YEARS)][["country", "series", "year"] + list(MEASURES)].copy()
    wid["survey_year"], wid["distance"], wid["old"] = np.nan, np.nan, False

    panel = pd.concat([pip, wid], ignore_index=True)
    pop = es.load("wid_reference_year_indicators")
    pop = pop.loc[pop["series"] == POP_SERIES, ["country", "year", "population"]]
    pop["year"] = pop["year"].astype(int)
    regions = es.load("country_regions").set_index("country")["region"]
    panel = panel.merge(pop, on=["country", "year"], how="left", validate="many_to_one")
    panel["region"] = panel["country"].map(regions)
    assert panel["population"].notna().all() and panel["region"].notna().all(), "population or region missing"
    assert (panel.groupby(["series", "year"]).size() == len(countries)).all(), "a series-year lacks countries"
    panel = panel.sort_values(["series", "country", "year"]).reset_index(drop=True)
    for c in ("survey_year", "distance"):
        panel[c] = panel[c].astype("Int64")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    panel[COLUMNS].to_csv(OUT_FILE, index=False, float_format="%.10g")
    print(f"Saved: {OUT_FILE.relative_to(DATA_DIR.parent)} ({len(panel):,} rows, {len(countries)} countries)")

    thresholds = us_thresholds(panel)
    write_figure(panel, countries, regions, thresholds)
    print(f"Saved: {FIG_FILE.relative_to(DATA_DIR.parent)} ({FIG_FILE.stat().st_size / 1024:.0f} KB)")
    summarise(panel, thresholds)


def us_thresholds(panel):
    us = panel[(panel["country"] == THRESHOLD_COUNTRY) & (panel["year"] == THRESHOLD_YEAR)].set_index("series")
    assert set(us.index) == set(SERIES), "no US 2022 value for some series"
    return {s: {k: float(us.at[s, k]) for k in MEASURES} for s in SERIES}


def write_figure(panel, countries, regions, thresholds):
    idx = {c: i for i, c in enumerate(countries)}
    base = panel[panel["series"] == "PIP"].sort_values(["country", "year"])
    pop = base.pivot(index="country", columns="year", values="population").loc[countries, YEARS]
    dist = base.pivot(index="country", columns="year", values="distance").loc[countries, YEARS]
    surv = base.pivot(index="country", columns="year", values="survey_year").loc[countries, YEARS]
    values = {}
    for s in SERIES:
        p = panel[panel["series"] == s]
        values[s] = {k: [[round(float(v), nd) for v in row]
                         for row in p.pivot(index="country", columns="year", values=k).loc[countries, YEARS].to_numpy()]
                     for k, (_, nd) in MEASURES.items()}
    fig = {
        "meta": {
            "title": "Countries with high inequality",
            "years": YEARS,
            "series": [{"key": k, "label": v, "pip": k.startswith("PIP")} for k, v in SERIES.items()],
            "measures": [{"key": k, "label": v[0]} for k, v in MEASURES.items()],
            "threshold": {"country": THRESHOLD_COUNTRY, "year": THRESHOLD_YEAR,
                          "values": {s: {k: round(v, 4) for k, v in t.items()} for s, t in thresholds.items()}},
            "old_after": OLD_AFTER,
            "stable": {k: {"type": t, "band": b} for k, (t, b) in STABLE.items()},
            "regions": sorted(set(regions[c] for c in countries)),
            "generated_by": "38_high_inequality_panel.py",
            "notes": [
                ("High inequality = at least the United States' value in 2022 in the same series and "
                 "measure. PIP series: each country's nearest survey at any distance (either side, ties "
                 "to the earlier); old = more than 5 years away. WID: the year itself."),
                ("171 countries with a national PIP survey. Population: the WID per-capita yardstick "
                 "at the year. Regions: PIP's seven."),
                "Full panel: data/processed/high_inequality_panel.csv.",
            ],
        },
        "countries": [{"c": c, "r": str(regions[c])} for c in countries],
        "population": [[round(float(v)) for v in row] for row in pop.to_numpy()],
        "distance": [[int(v) for v in row] for row in dist.to_numpy()],
        "survey_year": [[int(v) for v in row] for row in surv.to_numpy()],
        "values": values,
    }
    assert len(idx) == len(fig["countries"])
    FIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIG_FILE.write_text(json.dumps(fig, separators=(",", ":")))


def summarise(panel, thresholds):
    print(f"\nThresholds = {THRESHOLD_COUNTRY} in {THRESHOLD_YEAR}:")
    for s, t in thresholds.items():
        print(f"  {SERIES[s]:<14} " + "  ".join(f"{MEASURES[k][0]} {v:.3f}" for k, v in t.items()))
    show = [1990, 1995, 2000, 2005, 2010, 2015, 2019, 2022, 2024]
    for s in SERIES:
        p = panel[panel["series"] == s]
        hi = p["gini"] >= thresholds[s]["gini"]
        g = p.assign(hi=hi, hi_old=hi & p["old"], lo_old=~hi & p["old"]).groupby("year")
        t = pd.DataFrame({"high": g["hi"].sum(), "of_which_old": g["hi_old"].sum(),
                          "not_high_old": g["lo_old"].sum(),
                          "high_pop_share": g.apply(lambda x: x.loc[x["hi"], "population"].sum() / x["population"].sum(),
                                                    include_groups=False)}).loc[show]
        t["high_pop_share"] = (t["high_pop_share"] * 100).round(0).astype(int)
        print(f"\n{SERIES[s]} — countries at or above the US 2022 Gini ({thresholds[s]['gini']:.3f}):")
        print(t.T.to_string())

    # The World Bank blog's definition, on our PIP: Gini > 0.40, the nearest survey either side.
    p = panel[panel["series"] == "PIP"]
    print("\nCross-check with the World Bank blog (PIP Gini > 0.40, nearest survey either side, any distance):")
    for y, blog in WB_BLOG.items():
        s = p[p["year"] == y]
        n, recent = int((s["gini"] > 0.40).sum()), int(((s["gini"] > 0.40) & (s["distance"] <= 4)).sum())
        print(f"  {y}: {n} high-inequality countries ({recent} with a survey within 0-4 years); blog: {blog}")


if __name__ == "__main__":
    main()
