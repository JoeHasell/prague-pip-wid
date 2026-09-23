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
FILLED_FILE = DATA_DIR / "processed" / "filled_year_indicators.csv"
# Two bases for the PIP side: each country's nearest survey within +-5 years (33_), or PIP's filled
# lined-up series at the year itself (37_). The filled panel has no balanced variant: it already
# covers the same 171 countries every year.
BASES = {
    "nearest_survey": ("Nearest survey (within 5 years)",
                       "PIP from each country's nearest survey within five years of the year.",
                       ["common", "balanced", "own", "common_ex_ci"]),
    "filled": ("Filled every year (lined up)",
               "PIP's lined-up estimate for every year: surveys, plus interpolated and extrapolated "
               "years; the 171 countries with a national survey.",
               ["common", "own", "common_ex_ci"]),
}
FILLED_SAMPLE_NOTES = {
    "common": "The 171 countries with a national PIP survey, every year; WID restricted to them.",
    "own": "PIP on its 171 countries, WID on all 211 countries.",
    "common_ex_ci": "The 171 countries minus China and India, which carry about 38% of the population weight.",
}
KINDS = ("survey", "interpolated", "extrapolated")
COLUMNS = ["basis", "sample", "series", "ref_year", "unweighted", "weighted", "n_countries", "pop_coverage"]


def main():
    print("Reading the reference-year and filled datasets and the population yardstick")
    wid = es.load("wid_reference_year_indicators")
    pop = (wid.loc[wid["series"] == POP_SERIES, ["country", "year", "population"]]
              .rename(columns={"year": "ref_year"}))
    pop["ref_year"] = pop["ref_year"].astype(int)
    assert not pop.duplicated(["country", "ref_year"]).any()
    world = pop.groupby("ref_year")["population"].sum()

    near = read_basis(IN_FILE, pop)
    filled = read_basis(FILLED_FILE, pop, year_col="year")
    years = sorted(int(y) for y in near["ref_year"].unique())
    assert years == list(range(years[0], years[-1] + 1)), "reference years are not contiguous"
    assert sorted(filled["ref_year"].unique()) == years, "the two bases cover different years"

    near_samples, balanced = samples_for(near, years, with_balanced=True)
    filled_samples, _ = samples_for(filled, years, with_balanced=False)
    frames = []
    for basis, samples in (("nearest_survey", near_samples), ("filled", filled_samples)):
        assert list(samples) == BASES[basis][2], basis
        for key, d in samples.items():
            frames.append(averages(d, key, world).assign(basis=basis))
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["basis", "sample", "series", "ref_year"]).reset_index(drop=True)
    assert (out.groupby(["basis", "sample", "series"]).size() == len(years)).all(), "a sample is missing years"
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    out[COLUMNS].to_csv(OUT_FILE, index=False, float_format="%.10g")
    print(f"\nSaved: {OUT_FILE.relative_to(DATA_DIR.parent)} ({len(out):,} rows)")

    kinds = kind_mix(filled, filled_samples)
    write_figure(out, years, len(balanced), kinds)
    print(f"Saved: {FIG_FILE.relative_to(DATA_DIR.parent)} ({FIG_FILE.stat().st_size / 1024:.0f} KB)")

    # ---- summary
    print(f"\nBalanced panel (nearest survey): {len(balanced)} countries")
    show = [1990, 2000, 2010, 2019, 2024]
    for basis in BASES:
        for w in WEIGHTINGS:
            t = (out[(out["basis"] == basis) & (out["sample"] == "common")]
                 .pivot(index="series", columns="ref_year", values=w).loc[SERIES, show].round(3))
            print(f"\n-- {basis}, common, {w}\n{t.to_string()}")
    k = pd.DataFrame(kinds["common"]).assign(year=years).set_index("year").loc[show]
    print("\nFilled, common: population share by kind of PIP year\n" + (k * 100).round(0).astype(int).to_string())


def read_basis(path, pop, year_col="ref_year"):
    """One basis' country-level Ginis with the reference-year population attached."""
    d = pd.read_csv(path, keep_default_na=False, na_values=[""])
    if year_col != "ref_year":
        d = d.rename(columns={year_col: "ref_year"})
    assert set(d["series"].unique()) == set(SERIES), sorted(d["series"].unique())
    assert d["gini"].notna().all(), f"missing Gini in {path.name}"
    d = d.merge(pop, on=["country", "ref_year"], how="left", validate="many_to_one")
    assert d["population"].notna().all(), \
        f"no {POP_SERIES} population for {sorted(d.loc[d['population'].isna(), 'country'].unique())[:5]}"
    return d


def samples_for(ds, years, with_balanced):
    """The country samples of one basis, keyed as in BASES."""
    # Every PIP series covers the same country-years (they are one chain).
    pip_keys = ds.loc[ds["series"] == "PIP", ["country", "ref_year"]]
    for s in refyears.PIP_SIDE:
        k = ds.loc[ds["series"] == s, ["country", "ref_year"]]
        assert len(k) == len(pip_keys) and k.merge(pip_keys).shape[0] == len(pip_keys), f"{s} coverage differs from PIP"
    n_years = pip_keys.groupby("country")["ref_year"].nunique()
    balanced = sorted(n_years[n_years == len(years)].index)
    common = ds.merge(pip_keys, on=["country", "ref_year"])
    assert all(c in set(common["country"]) for c in EXCLUDED_BIG_TWO)
    samples = {"common": common}
    if with_balanced:
        samples["balanced"] = ds[ds["country"].isin(balanced)]
    samples["own"] = ds
    samples["common_ex_ci"] = common[~common["country"].isin(EXCLUDED_BIG_TWO)]
    return samples, balanced


def kind_mix(filled, samples):
    """Per filled sample and year: the PIP-side population share on survey / interpolated / extrapolated years."""
    out = {}
    for key, d in samples.items():
        p = d[d["series"] == "PIP"]
        tot = p.groupby("ref_year")["population"].sum()
        by = p.groupby(["ref_year", "kind"])["population"].sum().unstack().reindex(columns=list(KINDS)).fillna(0)
        share = by.div(tot, axis=0)
        out[key] = {k: [round(float(v), 3) for v in share[k]] for k in KINDS}
    return out


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


def write_figure(out, years, n_balanced, kinds):
    data, coverage = {}, {}
    for basis, (_, _, keys) in BASES.items():
        data[basis], coverage[basis] = {}, {}
        for key in keys:
            o = out[(out["basis"] == basis) & (out["sample"] == key)]
            data[basis][key] = {w: {s: [round(float(v), 4) for v in o[o["series"] == s].sort_values("ref_year")[w]]
                                    for s in SERIES} for w in WEIGHTINGS}
            # The PIP side and the WID side of a sample can differ in coverage (the `own` sample).
            coverage[basis][key] = {}
            for side, s in (("pip", "PIP"), ("wid", "WID_posttax_per_capita")):
                c = o[o["series"] == s].sort_values("ref_year")
                coverage[basis][key][side] = {"n": [int(v) for v in c["n_countries"]],
                                              "pop": [round(float(v), 3) for v in c["pop_coverage"]]}
            if basis == "filled":
                coverage[basis][key]["kinds"] = kinds[key]
    samples = {
        basis: [{"key": k, "label": SAMPLES[k][0],
                 "note": (FILLED_SAMPLE_NOTES[k] if basis == "filled" else SAMPLES[k][1])} for k in keys]
        for basis, (_, _, keys) in BASES.items()
    }
    fig = {
        "meta": {
            "title": "Average Gini across countries, 1990-2024",
            "years": years,
            "series": [{"key": s, "label": SERIES_LABELS[s][0], "short": SERIES_LABELS[s][1]} for s in SERIES],
            "bases": [{"key": k, "label": v[0], "note": v[1]} for k, v in BASES.items()],
            "samples": samples,
            "weightings": [{"key": k, "label": v[0], "note": v[1]} for k, v in WEIGHTINGS.items()],
            "n_balanced": n_balanced,
            "etl_version": es.ETL_VERSION,
            "generated_by": "36_global_gini_averages.py",
            "notes": [
                ("The mean of country Ginis at each year, NOT the Gini of the world distribution. "
                 "Nearest survey: data/processed/reference_year_indicators.csv (33_), each country's "
                 "nearest PIP survey within +-5 years. Filled: data/processed/filled_year_indicators.csv "
                 "(37_), PIP's lined-up estimate for every year of the 171 countries with a national "
                 "survey. WID at the year itself in both."),
                ("Filled years are mostly the nearest survey's distribution carried forward or back: "
                 "extrapolated years keep the edge survey's Gini (exactly in two thirds of them), "
                 "interpolated years blend two surveys. coverage.filled.<sample>.kinds gives the "
                 "population share on each kind of year."),
                ("Population weights: the WID per-capita bins' population at the year, one "
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
