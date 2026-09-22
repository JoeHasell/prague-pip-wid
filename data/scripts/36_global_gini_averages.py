"""
36_global_gini_averages.py — the average country Gini across the world, unweighted and
population-weighted, for every reference year and every series of the reference-year dataset.

    data/processed/global_gini_averages.csv   the dataset
    data/figures/fig_global_gini_average.json  <- fig-global-gini-average
                                                  (components/fig-global-gini-average.js)

WHAT IT IS
----------
For each reference year 1990-2024 and each of the seven series in
data/processed/reference_year_indicators.csv (33_), the mean of the country Ginis:

    unweighted   every country counts once
    weighted     countries weighted by population at the REFERENCE year

This is an average of within-country inequality, NOT the Gini of the world income
distribution: it says how unequal the typical country (or the country the typical
person lives in) is, and is blind to the gaps between country means.

ONE POPULATION YARDSTICK for every series: the population carried on the WID per-capita
bins at the reference year (the ETL's, independent of both sources — see etl_mld.py,
WEIGHTS). The series' own bin populations differ between the PIP and WID sides for dozens
of countries, which is why 33_ does not ship them. Reference-year population, not
survey-year: a 2019 average is about the world of 2019 even where the survey is from 2017.

FOUR COUNTRY SAMPLES, because PIP's coverage moves with the survey calendar (98 countries
in 1990, 160 in 2015, 126 in 2024) and WID covers all 211 every year:

    common        the countries with a PIP survey match in that reference year; the WID
                  series restricted to the same countries. The like-for-like comparison.
    balanced      the countries with a PIP match in EVERY reference year, identical along
                  the time axis, so a trend cannot come from countries entering or leaving.
    own           each source on its own coverage (PIP = common; WID = all 211).
    common_ex_ci  the common sample without China and India, which together carry about
                  38% of the weight — the weighted average is largely a statement about them.

ONE ROW PER sample x series x ref_year in the CSV:

    sample, series, ref_year
    unweighted, weighted    the two averages, Gini 0-1
    n_countries             countries averaged
    pop_coverage            their population as a share of the 211-country world total

Run:  python data/scripts/36_global_gini_averages.py   (after 33_; refresh_from_etl.py runs it)
"""

import json
from pathlib import Path

import pandas as pd

import etl_source as es
import refyears

DATA_DIR = Path(__file__).resolve().parents[1]
IN_FILE = DATA_DIR / "processed" / "reference_year_indicators.csv"
OUT_FILE = DATA_DIR / "processed" / "global_gini_averages.csv"
FIG_FILE = DATA_DIR / "figures" / "fig_global_gini_average.json"

POP_SERIES = "WID_pretax_per_capita"
EXCLUDED_BIG_TWO = ("China", "India")
SERIES = list(refyears.PIP_SIDE) + list(refyears.WID_SIDE)
SERIES_LABELS = {
    "PIP": ("PIP, as published", "PIP as published"),
    "PIP_consinc": ("PIP on an income basis (WID profile)", "PIP income basis"),
    "PIP_topadj": ("PIP on an income basis with WID's top 1% appended (WID profile)", "PIP + WID top 1%"),
    "PIP_consinc_wb": ("PIP on an income basis (Wollburg et al. 2023 inverse)", "PIP income basis (Wollburg)"),
    "PIP_topadj_wb": ("PIP on the Wollburg basis with WID's top 1% appended", "PIP + WID top 1% (Wollburg)"),
    "WID_pretax_per_capita": ("WID pre-tax national income, per capita", "WID pre-tax"),
    "WID_posttax_per_capita": ("WID post-tax national income, per capita", "WID post-tax"),
}
SAMPLES = {
    "common": ("Same countries as PIP",
               "Countries with a PIP survey within five years of the reference year; WID restricted to them."),
    "balanced": ("Balanced panel",
                 "Only the countries with a PIP survey match in every year 1990-2024, so the sample never changes."),
    "own": ("Each source's own coverage",
            "PIP on its matched countries, WID on all 211 countries."),
    "common_ex_ci": ("Same countries, without China and India",
                     "The common sample minus China and India, which carry about 38% of the population weight."),
}
WEIGHTINGS = {
    "unweighted": ("Unweighted", "Every country counts once."),
    "weighted": ("Population-weighted", "Countries weighted by their population in the reference year."),
}
COLUMNS = ["sample", "series", "ref_year", "unweighted", "weighted", "n_countries", "pop_coverage"]


def main():
    print("Reading the reference-year dataset and the population yardstick")
    ds = pd.read_csv(IN_FILE, keep_default_na=False, na_values=[""])
    assert set(ds["series"].unique()) == set(SERIES), sorted(ds["series"].unique())
    assert ds["gini"].notna().all(), "missing Gini in the reference-year dataset"

    wid = es.load("wid_reference_year_indicators")
    pop = (wid.loc[wid["series"] == POP_SERIES, ["country", "year", "population"]]
              .rename(columns={"year": "ref_year"}))
    pop["ref_year"] = pop["ref_year"].astype(int)
    assert not pop.duplicated(["country", "ref_year"]).any()
    ds = ds.merge(pop, on=["country", "ref_year"], how="left", validate="many_to_one")
    assert ds["population"].notna().all(), \
        f"no {POP_SERIES} population for {sorted(ds.loc[ds['population'].isna(), 'country'].unique())[:5]}"
    world = pop.groupby("ref_year")["population"].sum()

    years = sorted(int(y) for y in ds["ref_year"].unique())
    assert years == list(range(years[0], years[-1] + 1)), "reference years are not contiguous"

    # Every PIP series covers the same country-reference-years (they are one chain).
    pip_keys = ds.loc[ds["series"] == "PIP", ["country", "ref_year"]]
    for s in refyears.PIP_SIDE:
        k = ds.loc[ds["series"] == s, ["country", "ref_year"]]
        assert len(k) == len(pip_keys) and k.merge(pip_keys).shape[0] == len(pip_keys), f"{s} coverage differs from PIP"
    n_years = pip_keys.groupby("country")["ref_year"].nunique()
    balanced = sorted(n_years[n_years == len(years)].index)

    common = ds.merge(pip_keys, on=["country", "ref_year"])
    samples = {
        "common": common,
        "balanced": ds[ds["country"].isin(balanced)],
        "own": ds,
        "common_ex_ci": common[~common["country"].isin(EXCLUDED_BIG_TWO)],
    }
    assert set(samples) == set(SAMPLES)
    assert all(c in set(common["country"]) for c in EXCLUDED_BIG_TWO)

    out = pd.concat([averages(d, key, world) for key, d in samples.items()], ignore_index=True)
    out = out.sort_values(["sample", "series", "ref_year"]).reset_index(drop=True)
    # Every sample has every series in every year.
    assert (out.groupby(["sample", "series"]).size() == len(years)).all(), "a sample is missing years"
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out[COLUMNS].to_csv(OUT_FILE, index=False, float_format="%.10g")
    print(f"\nSaved: {OUT_FILE.relative_to(DATA_DIR.parent)} ({len(out):,} rows)")

    write_figure(out, years, len(balanced))
    print(f"Saved: {FIG_FILE.relative_to(DATA_DIR.parent)} ({FIG_FILE.stat().st_size / 1024:.0f} KB)")

    # ---- summary
    print(f"\nBalanced panel: {len(balanced)} countries")
    show = [1990, 2000, 2010, 2019, 2024]
    for key in ("common", "common_ex_ci"):
        for w in WEIGHTINGS:
            t = (out[out["sample"] == key].pivot(index="series", columns="ref_year", values=w)
                    .loc[SERIES, show].round(3))
            print(f"\n-- {key}, {w}\n{t.to_string()}")
    cov = out[(out["sample"] == "common") & (out["series"] == "PIP")].set_index("ref_year")
    print("\nPIP coverage (common sample): " +
          ", ".join(f"{y}: {int(cov.at[y, 'n_countries'])} ({cov.at[y, 'pop_coverage']:.0%})" for y in show))


def averages(d, sample, world):
    """Unweighted and population-weighted mean Gini by series and reference year."""
    d = d.assign(gp=d["gini"] * d["population"])
    g = d.groupby(["series", "ref_year"])
    r = pd.DataFrame({
        "unweighted": g["gini"].mean(),
        "weighted": g["gp"].sum() / g["population"].sum(),
        "n_countries": g.size(),
        "pop_coverage": g["population"].sum(),
    }).reset_index()
    r["pop_coverage"] = r["pop_coverage"] / r["ref_year"].map(world)
    assert (r["pop_coverage"] <= 1 + 1e-9).all()
    r.insert(0, "sample", sample)
    return r


def write_figure(out, years, n_balanced):
    data, coverage = {}, {}
    for key in SAMPLES:
        o = out[out["sample"] == key]
        data[key] = {w: {s: [round(float(v), 4) for v in o[o["series"] == s].sort_values("ref_year")[w]]
                         for s in SERIES} for w in WEIGHTINGS}
        # The PIP side and the WID side of a sample can differ in coverage (the `own` sample).
        coverage[key] = {}
        for side, s in (("pip", "PIP"), ("wid", "WID_posttax_per_capita")):
            c = o[o["series"] == s].sort_values("ref_year")
            coverage[key][side] = {"n": [int(v) for v in c["n_countries"]],
                                   "pop": [round(float(v), 3) for v in c["pop_coverage"]]}
    fig = {
        "meta": {
            "title": "Average Gini across countries, 1990-2024",
            "years": years,
            "series": [{"key": s, "label": SERIES_LABELS[s][0], "short": SERIES_LABELS[s][1]} for s in SERIES],
            "samples": [{"key": k, "label": v[0], "note": v[1]} for k, v in SAMPLES.items()],
            "weightings": [{"key": k, "label": v[0], "note": v[1]} for k, v in WEIGHTINGS.items()],
            "n_balanced": n_balanced,
            "etl_version": es.ETL_VERSION,
            "generated_by": "36_global_gini_averages.py",
            "notes": [
                ("The mean of country Ginis at each reference year, NOT the Gini of the world "
                 "distribution. Built from data/processed/reference_year_indicators.csv (33_): each "
                 "country's nearest PIP survey within +-5 years, WID at the reference year itself."),
                ("Population weights: the WID per-capita bins' population at the reference year, one "
                 "yardstick for every series."),
                "Full table: data/processed/global_gini_averages.csv.",
            ],
        },
        "data": data,
        "coverage": coverage,
    }
    FIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    FIG_FILE.write_text(json.dumps(fig, separators=(",", ":")))


if __name__ == "__main__":
    main()
