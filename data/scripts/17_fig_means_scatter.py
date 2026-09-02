"""
17_fig_means_scatter.py — survey means (PIP) vs national-accounts means (WID),
for TWO years: COMPARISON_YEAR (1990, the first year in PIP) and TARGET_YEAR.

One dot per country. X = PIP's survey mean (disposable income or consumption,
per capita); Y = WID's national income mean per capita. Both international-$
PER MONTH. The chart is drawn two ways from this one file (see the component):
levels (y vs x), ratio (y/x vs x) and share (x/y vs x).

WHY anninci999 AND NOT THE HARMONIZED FILE: the harmonized dataset is 2023
only. This figure needs an early year too, and it needs only country MEANS,
not distributions — so it reads WID's national-income-per-capita variable
directly (data/raw/wid/WID_national_income_means.csv, see 18_fetch_wid_means.py)
and computes PIP means from the two committed thousand-bins extracts.
For 2023 this route reproduces the harmonized pipeline to ~1e-5 relative
(asserted below), which is the cross-check that keeps the two consistent.

WHY ONE WID SERIES: WID's post-tax national income (diinc) redistributes all
taxes AND all spending, so its country total equals pre-tax national income by
construction (verified in 99_verify.py). Pre-tax and post-tax have the SAME
mean; the y axis is the same under either concept.

REGRESSIONS: each view is fitted on ITS OWN plotted variables — levels
regresses log10(WID) on log10(PIP), ratio regresses log10(WID/PIP) on
log10(PIP), share regresses log10(100*PIP/WID) on log10(PIP) — unweighted and
weighted by population, per year. Nothing is derived by transforming another
view's coefficients.

Note (worth knowing, not a reason to fit only once): because the transformed
dependent variable differs from the levels one by exactly log10(x), which IS
the regressor, OLS returns slope-1 / 1-slope and the same (or 2-intercept)
intercept. So the fitted LINES coincide with the transformed levels line to
machine precision. What genuinely differs is R^2, which is not invariant:
in 2023 the levels fit has R^2 0.86-0.87 while the ratio and share fits have
0.026 (unweighted) and 0.064 (weighted). The share/ratio R^2 is the honest
one for those charts — survey mean explains only a few percent of the
variation in the gap.

INPUT   data/raw/wid/WID_national_income_means.csv   (18_fetch_wid_means.py)
        data/raw/wid/WID_ppp.csv                     (xlcusp, PPP_YEAR rows)
        data/raw/wid/country_mapping.csv
        data/raw/pip/pip_thousand_bins_{1990,2023}.csv.gz
        data/raw/regions/country_region_mapping.csv
        data/processed/pip_wid_harmonized_2023.csv   (cross-check only)
OUTPUT  data/figures/fig_means_scatter.json

Run:  python data/scripts/17_fig_means_scatter.py
"""

import json
import numpy as np
import pandas as pd

from config import (
    DATA_DIR, DAILY_TO_MONTHLY, TARGET_YEAR, COMPARISON_YEAR, PPP_YEAR,
    WID_MEANS_FILE, WID_PPP_FILE, COUNTRY_MAPPING_FILE,
    PIP_RAW_FILE, PIP_RAW_FILE_EARLY, HARMONIZED_FILE,
)

REGION_FILE = DATA_DIR / "raw" / "regions" / "country_region_mapping.csv"
OUT_FILE = DATA_DIR / "figures" / "fig_means_scatter.json"
YEARS = [COMPARISON_YEAR, TARGET_YEAR]


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


def pip_means(path, year):
    d = pd.read_csv(path)
    d = d[d.year == year]
    assert len(d), f"no PIP rows for {year} in {path.name}"
    g = d.assign(_x=d["avg"] * d["pop"]).groupby("country")
    return (g["_x"].sum() / g["pop"].sum()).rename("pip") * DAILY_TO_MONTHLY


def wid_means(means, ppp, cmap, year):
    w = means[means.year == year].merge(ppp, on="country", how="left", validate="one_to_one")
    missing = w.loc[w.ppp.isna(), "country"].tolist()
    assert not missing, f"no xlcusp({PPP_YEAR}) for: {missing}"
    w["wid"] = w.nninc_lcu_per_capita / w.ppp / 12          # LCU/yr -> PPP-$/month
    w = w.merge(cmap, on="country", how="inner")
    return w.set_index("name")[["wid", "population"]]


def build_year(year, ppp, cmap, regions):
    pip = pip_means(PIP_RAW_FILE_EARLY if year == COMPARISON_YEAR else PIP_RAW_FILE, year)
    wid = wid_means(pd.read_csv(WID_MEANS_FILE), ppp, cmap, year)
    df = wid.join(pip, how="inner").rename(columns={"population": "pop"})
    before = len(df)
    df = df[(df.pip > 0) & (df.wid > 0)].copy()
    if len(df) < before:
        print(f"  [{year}] dropped {before - len(df)} countries with a non-positive mean")
    df["region"] = df.index.map(regions).fillna("Other")
    df["ratio"] = df.wid / df.pip
    return df.sort_index()


# Superseded by the ETL pipeline — see legacy_guard.py.
from legacy_guard import require_ack


def main():
    require_ack(
        script='17_fig_means_scatter.py',
        figures=['fig_means_scatter.json'],
        replaced_by='28_fig_means_from_etl.py',
    )
    ppp = pd.read_csv(WID_PPP_FILE)
    ppp = ppp[ppp.year == PPP_YEAR][["country", "ppp"]]
    cmap = (pd.read_csv(COUNTRY_MAPPING_FILE)[["country", "PIP country name"]]
              .rename(columns={"PIP country name": "name"}).dropna())
    regions = pd.read_csv(REGION_FILE).set_index("country")["region"]

    frames = {y: build_year(y, ppp, cmap, regions) for y in YEARS}

    # --- cross-check the 2023 slice against the harmonized pipeline ---------
    h = pd.read_csv(HARMONIZED_FILE)
    ref = {}
    for src, key in [("PIP", "pip"), ("WID_pretax_per_capita", "wid")]:
        d = h[h.source == src]
        g = d.assign(_x=d["average"] * d["pop"]).groupby("country")
        ref[key] = (g["_x"].sum() / g["pop"].sum()) * DAILY_TO_MONTHLY
    chk = frames[TARGET_YEAR].join(pd.DataFrame(ref), rsuffix="_ref", how="inner")
    for key in ["pip", "wid"]:
        rel = ((chk[key] - chk[key + "_ref"]).abs() / chk[key + "_ref"]).max()
        assert rel < 1e-4, f"{key} disagrees with the harmonized pipeline by {rel:.2e}"
        print(f"  cross-check {key} vs harmonized 2023: max rel diff {rel:.2e}  [OK]")

    region_order = sorted(set().union(*(set(f.region) for f in frames.values())))
    ridx = {r: i for i, r in enumerate(region_order)}

    # y-variable for each view, as plotted
    VIEWS = {
        "levels": lambda d: d.wid.values,
        "ratio":  lambda d: (d.wid / d.pip).values,
        "share":  lambda d: (100 * d.pip / d.wid).values,
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
            "years": [str(y) for y in YEARS],
            "default_year": str(TARGET_YEAR),
            "units": f"international-$ PER MONTH (PIP: 2021 PPPs; WID: {PPP_YEAR} PPPs)",
            "notes": [
                "WID pre-tax and post-tax national income have identical means by "
                "construction (DINA), so the y axis is the same under either concept.",
                f"{COMPARISON_YEAR} is the first year in PIP's thousand-bins dataset. "
                "Survey coverage that far back is thin: many country-years are "
                "interpolated or extrapolated by the source, on both sides.",
                "Each view is regressed on its own plotted variables (levels, ratio, "
                "share), not transformed from one another; the weighted fit uses WID "
                "population (npopuli999). R^2 differs sharply between views: the "
                "levels fit is dominated by how rich a country is, the ratio and "
                "share fits are the informative ones about the gap itself.",
                "The 2023 slice is asserted equal to the harmonized pipeline "
                "(data/processed/pip_wid_harmonized_2023.csv) to 1e-4 relative.",
            ],
            "generated_by": "data/scripts/17_fig_means_scatter.py",
        },
        "regions": region_order,
        "years": years_out,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Saved: {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
