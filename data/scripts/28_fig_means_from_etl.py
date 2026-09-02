"""
28_fig_means_from_etl.py — survey means (PIP) vs national-accounts means (WID),
sourced from OWID's ETL. Replaces 17_fig_means_scatter.py.

WHY THIS EXISTS
---------------
This was the last figure in the deck still computed from the local pipeline
(17_fig_means_scatter.py -> processed/pip_wid_harmonized_2023.csv + the WID
Stata pull + a hand-made means file). That left it on a different data vintage
from every other chart: the WID between-country shares moved 3-4pp when the Q2
figures were ported to the ETL, so this chart's WID means came from the old
vintage while its neighbours on the same slides came from the new one. It also
sat outside refresh_from_etl.py, so an ETL refresh moved every chart except
this one, silently.

Everything it needs is already in the committed ETL cache:
inequality_decomposition_by_country publishes each country's MEAN per series
per year, on one population yardstick, for 1990-2024.

WHAT THE CHART SHOWS (unchanged)
--------------------------------
One dot per country. X = PIP's survey mean (disposable income or consumption,
per capita); Y = WID's national income mean per capita. Both international-$
PER MONTH. The component draws this three ways from the one file: levels
(y vs x), ratio (y/x vs x) and share (x/y vs x).

WHY ONE WID SERIES: WID's post-tax national income redistributes all taxes AND
all spending, so its country total equals pre-tax national income by
construction. Pre-tax and post-tax therefore have the SAME mean and the y axis
is identical under either concept — asserted below rather than assumed.

REGIONS: from the ETL's treemap_regions, which reproduces this project's own
eight-region scheme (PIP's seven plus a Western Europe split) exactly — checked
against the local raw/regions/country_region_mapping.csv on 2026-09-02: 218
countries in common, zero disagreements. So the port drops the local region
file without changing a single dot's colour.

REGRESSIONS: each view is fitted on ITS OWN plotted variables — levels
regresses log10(WID) on log10(PIP), ratio regresses log10(WID/PIP) on
log10(PIP), share regresses log10(100*PIP/WID) on log10(PIP) — unweighted and
weighted by population, per year. Nothing is derived by transforming another
view's coefficients.

Note (carried over from the original script, still worth knowing): because the
transformed dependent variable differs from the levels one by exactly log10(x),
which IS the regressor, OLS returns slope-1 / 1-slope and the same (or
2-intercept) intercept, so the fitted LINES coincide. What genuinely differs is
R^2, which is not invariant — and the share/ratio R^2 is the honest one for
those charts.

WHY ONLY TWO YEARS: the ETL holds 1990-2024, but the component draws one year
at a time (the slides pass `year` explicitly) AND scales its axes across every
year present in the file. Emitting all 35 would make the file ~17x bigger for
data nothing reads, and would move the axis domains of the existing slides. Add
a year to DECK_YEARS below and re-run if a slide needs one.

INPUT   data/raw/etl/inequality_decomposition_by_country.csv.gz  (ETL cache)
        data/raw/etl/treemap_regions.csv.gz                      (ETL cache)
OUTPUT  data/figures/fig_means_scatter.json   (same filename and same JSON
        shape as before, so no slide and no component needs editing)

Run:  python data/scripts/28_fig_means_from_etl.py
      (or, with everything else: python data/scripts/refresh_from_etl.py)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
OUT_FILE = FIGURES_DIR / "fig_means_scatter.json"

# The years the deck's slides ask for. See "WHY ONLY TWO YEARS" above.
DECK_YEARS = [1990, es.DISPLAY_YEAR]

# X and Y of the scatter, as ETL/deck series names.
PIP_SERIES = "PIP"
WID_SERIES = "WID_pretax_per_capita"
# Used only to assert the pre-tax/post-tax mean identity.
WID_POSTTAX_SERIES = "WID_posttax_per_capita"


def ols_loglog(x, y, w=None):
    """OLS of log10(y) on log10(x); w = weights (None -> unweighted)."""
    lx, ly = np.log10(x), np.log10(y)
    w = np.ones_like(lx) if w is None else np.asarray(w, dtype=float)
    mx, my = np.average(lx, weights=w), np.average(ly, weights=w)
    slope = np.average((lx - mx) * (ly - my), weights=w) / np.average((lx - mx) ** 2, weights=w)
    intercept = my - slope * mx
    ss_res = np.average((ly - (intercept + slope * lx)) ** 2, weights=w)
    ss_tot = np.average((ly - my) ** 2, weights=w)
    return {"slope": float(slope), "intercept": float(intercept),
            "r2": float(1 - ss_res / ss_tot), "n": int(len(lx))}


def series_slice(dec, series, year):
    """One series in one year, indexed by country: mean per month + population."""
    d = dec[(dec.series == series) & (dec.year == year)]
    assert len(d), f"no {series} rows for {year} in the ETL cache"
    assert not d.country.duplicated().any(), f"duplicate countries in {series} {year}"
    out = d.set_index("country")[["mean", "population_weight"]].copy()
    out["mean"] = out["mean"] * es.DAILY_TO_MONTHLY
    return out


def build_year(dec, regions, year):
    pip = series_slice(dec, PIP_SERIES, year)
    wid = series_slice(dec, WID_SERIES, year)

    # The ETL puts every per-capita series on ONE population yardstick, so the
    # two axes must agree about how many people each country has. Assert it
    # rather than picking one silently.
    common = pip.index.intersection(wid.index)
    pop_gap = ((pip.loc[common, "population_weight"] - wid.loc[common, "population_weight"]).abs()
               / wid.loc[common, "population_weight"]).max()
    assert pop_gap < 1e-9, (
        f"[{year}] PIP and {WID_SERIES} disagree about population by {pop_gap:.2e} "
        "relative — the per-capita yardstick is supposed to be shared"
    )

    # WID pre-tax and post-tax national income have the same country total by
    # construction, hence the same mean: the y axis is concept-independent.
    #
    # In the ETL this identity holds to ~3e-4, not to machine precision: measured
    # 2026-09-02, about 150 of 211 countries differ by more than 1e-6 in every
    # year checked (1990/2000/2010/2023/2024), the worst always ~3e-4 and always
    # a very poor country (Burundi, Mozambique, Malawi, Somalia) — consistent
    # with a positive income floor mattering more where the mean is low. The old
    # local pipeline held it to 2e-6 (99_verify.py check 4). Immaterial for this
    # chart (0.03% on an axis spanning orders of magnitude), so the tolerance is
    # set to catch a real breakdown rather than this floor effect.
    post = series_slice(dec, WID_POSTTAX_SERIES, year)
    both = wid.index.intersection(post.index)
    mean_gap = ((wid.loc[both, "mean"] - post.loc[both, "mean"]).abs()
                / post.loc[both, "mean"]).max()
    assert mean_gap < 1e-3, (
        f"[{year}] WID pre-tax and post-tax per-capita means differ by "
        f"{mean_gap:.2e} relative — the DINA identity should make them equal"
    )
    print(f"  [{year}] pre-tax vs post-tax mean identity holds to {mean_gap:.2e} relative")

    df = pd.DataFrame({
        "pip": pip["mean"],
        "wid": wid["mean"],
        "pop": wid["population_weight"],
    }).dropna()

    before = len(df)
    df = df[(df.pip > 0) & (df.wid > 0) & (df["pop"] > 0)].copy()
    if len(df) < before:
        print(f"  [{year}] dropped {before - len(df)} countries with a non-positive mean or population")

    missing_region = sorted(set(df.index) - set(regions.index))
    if missing_region:
        print(f"  [{year}] no region for {len(missing_region)}: {missing_region[:5]} -> 'Other'")
    df["region"] = df.index.map(regions).fillna("Other")
    df["ratio"] = df.wid / df.pip
    return df.sort_index()


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    dec = es.load("inequality_decomposition_by_country")  # deck series names already
    regions = es.load("treemap_regions").set_index("country")["region"]

    frames = {y: build_year(dec, regions, y) for y in DECK_YEARS}

    region_order = sorted(set().union(*(set(f.region) for f in frames.values())))
    ridx = {r: i for i, r in enumerate(region_order)}

    # y-variable for each view, as plotted
    VIEWS = {
        "levels": lambda d: d.wid.values,
        "ratio": lambda d: (d.wid / d.pip).values,
        "share": lambda d: (100 * d.pip / d.wid).values,
    }

    years_out = {}
    for y, df in frames.items():
        fits = {v: {"unweighted": ols_loglog(df.pip.values, f(df)),
                    "weighted": ols_loglog(df.pip.values, f(df), df["pop"].values)}
                for v, f in VIEWS.items()}
        s = df.sort_values("ratio")
        popmed = float(s.assign(cw=s["pop"].cumsum() / s["pop"].sum())
                        .query("cw >= 0.5").ratio.iloc[0])
        years_out[str(y)] = {
            "n_countries": int(len(df)),
            "fits": fits,
            "ratio_summary": {"median": float(df.ratio.median()),
                              "pop_weighted_median": popmed,
                              "min": float(df.ratio.min()), "max": float(df.ratio.max())},
            "points": [[c, ridx[r["region"]], round(r.pip, 2), round(r.wid, 2), int(r["pop"])]
                       for c, r in df.iterrows()],
        }
        print(f"  [{y}] {len(df)} countries | median ratio {df.ratio.median():.2f}x "
              f"(pop-wtd {popmed:.2f}x)")
        for v in VIEWS:
            print(f"        {v:<7} slope {fits[v]['unweighted']['slope']:+.3f} "
                  f"(R2 {fits[v]['unweighted']['r2']:.3f}) | weighted "
                  f"{fits[v]['weighted']['slope']:+.3f} (R2 {fits[v]['weighted']['r2']:.3f})")

    out = {
        "meta": {
            "title": "Surveys capture only part of national income",
            "x_label": "PIP survey mean — disposable income or consumption, per capita",
            "y_label": "WID national income mean, per capita",
            "ratio_label": "WID national income ÷ PIP survey mean",
            "share_label": "PIP survey mean as a share of WID national income",
            "years": [str(y) for y in DECK_YEARS],
            "default_year": str(es.DISPLAY_YEAR),
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
            "units": "international-$ PER MONTH (PIP: 2021 PPPs; WID: latest PPP vintage); "
                     "converted from the ETL's daily values at 365/12",
            "notes": [
                "WID pre-tax and post-tax national income have identical means by "
                "construction (DINA), so the y axis is the same under either concept. "
                "Asserted in the script, not assumed.",
                "1990 is the first year the ETL covers. Survey coverage that far back "
                "is thin: many country-years are interpolated or extrapolated by the "
                "source, on both sides.",
                "Both axes use the ETL's single population yardstick (OWID population "
                "for per-capita series), so the dot positions and the population "
                "weights refer to the same denominator. Asserted in the script.",
                "Each view is regressed on its own plotted variables (levels, ratio, "
                "share), not transformed from one another; the weighted fit uses the "
                "ETL population weight. R^2 differs sharply between views: the levels "
                "fit is dominated by how rich a country is, the ratio and share fits "
                "are the informative ones about the gap itself.",
                "Sourced from the ETL (replaces 17_fig_means_scatter.py, which read "
                "the local pipeline's 2023 harmonized file and a hand-made WID means "
                "file). Refreshed by data/scripts/refresh_from_etl.py.",
            ],
            "generated_by": "data/scripts/28_fig_means_from_etl.py",
        },
        "regions": region_order,
        "years": years_out,
    }
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Saved: {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
