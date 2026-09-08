"""
29_fig_mld_scatter.py — within-country inequality, PIP vs WID, country by country.

WHAT THE CHART SHOWS
--------------------
One bubble per country, area proportional to population.
  X = the within-country mean log deviation of PIP   (survey, per capita)
  Y = the within-country mean log deviation of WID   (national income, per capita)
Dotted diagonals mark the multiples WID is of PIP (1x, 2x, 3x, 5x, 10x).

WHY IT EARNS A PLACE NEXT TO THE BRIDGING FIGURE
------------------------------------------------
The bridging figure shows the GLOBAL within component of each series — one bar per
column. It cannot show whether the WID/PIP gap in that bar is a uniform shift or a
few countries doing the work, nor whether the countries carrying most of the
world's population sit where the unweighted average sits. This is the same
quantity at country level: exactly the numbers the decomposition aggregates into
the within bar.

WHY NO NEW METHOD
-----------------
Nothing is computed here beyond selecting rows. The ETL's
`inequality_decomposition_by_country` already publishes each country's within-MLD
per series per year, from the same decomposition that produces the global bars, on
one population yardstick. So this figure and the bridging figure cannot drift
apart.

WHY TWO OUTPUT FILES
--------------------
Pre-tax and post-tax WID have the same country MEAN by construction, so the means
scatter needs one file. Within-country INEQUALITY is the opposite: the pre/post-tax
gap is one of the deck's findings. Both are written, in the same shape and with
the same axis domains, so two slides can flick between them.

WHY NO NEW COMPONENT
--------------------
Both files are written in the shape `fig-means-scatter` already reads — log-log
axes, population bubbles, dotted ratio diagonals, region colours, the log-log
fits. A slide points that component at one of these files and passes
`valueFormat: "plain"` (the MLD is dimensionless, not dollars).

INPUT   data/raw/etl/inequality_decomposition_by_country.csv.gz  (ETL cache)
        data/raw/etl/treemap_regions.csv.gz                      (ETL cache)
OUTPUT  data/figures/fig_mld_scatter.json           (WID pre-tax on y)
        data/figures/fig_mld_scatter_posttax.json   (WID post-tax on y)

Run:  python data/scripts/29_fig_mld_scatter.py
      (or, with everything else: python data/scripts/refresh_from_etl.py)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"

# Matches 28_fig_means_from_etl.py, so the two scatters cover the same years.
DECK_YEARS = [1990, es.DISPLAY_YEAR]

PIP_SERIES = "PIP"
# (output filename suffix, ETL series, tax word, chart title)
WID_VARIANTS = [
    ("", "WID_pretax_per_capita", "pre-tax",
     "Within-country inequality is far higher in WID (pre-tax)"),
    # Post-tax is still higher on the median country but only ~2.5x, and some
    # countries fall below 1x, so it does not get the pre-tax headline.
    ("_posttax", "WID_posttax_per_capita", "post-tax",
     "The same comparison, with WID measured post-tax"),
]


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
    """One series in one year, indexed by country: within-MLD + population."""
    d = dec[(dec.series == series) & (dec.year == year)]
    assert len(d), f"no {series} rows for {year} in the ETL cache"
    assert not d.country.duplicated().any(), f"duplicate countries in {series} {year}"
    return d.set_index("country")[["mld_within", "population_weight"]].copy()


def pop_weighted_median(df, col):
    s = df.sort_values(col)
    cw = s["pop"].cumsum() / s["pop"].sum()
    return float(s.loc[cw >= 0.5, col].iloc[0])


def ratio_stats(df):
    """Summary of the country-level WID/PIP ratio.

    These average the country RATIOS. That is not the ratio of the global within
    components in the bridging figure, which is a ratio of population-weighted
    MLD LEVELS — pop_weighted_mean is the one that comes closest to it.
    """
    return {
        "mean": float(df.ratio.mean()),
        "pop_weighted_mean": float(np.average(df.ratio.values, weights=df["pop"].values)),
        "median": float(df.ratio.median()),
        "pop_weighted_median": pop_weighted_median(df, "ratio"),
        "min": float(df.ratio.min()),
        "max": float(df.ratio.max()),
    }


def build_year(dec, regions, wid_series, year):
    pip = series_slice(dec, PIP_SERIES, year)
    wid = series_slice(dec, wid_series, year)

    # Every per-capita series shares ONE population yardstick in the ETL, and the
    # bubble areas depend on it. Assert rather than silently picking one.
    common = pip.index.intersection(wid.index)
    gap = ((pip.loc[common, "population_weight"] - wid.loc[common, "population_weight"]).abs()
           / wid.loc[common, "population_weight"]).max()
    assert gap < 1e-9, (
        f"[{year}] PIP and {wid_series} disagree about population by {gap:.2e} "
        "relative — the per-capita yardstick is supposed to be shared"
    )

    df = pd.DataFrame({
        "pip": pip["mld_within"],
        "wid": wid["mld_within"],
        "pop": pip["population_weight"],
    }).dropna()

    before = len(df)
    # Log axes and ratios both need strictly positive values.
    df = df[(df.pip > 0) & (df.wid > 0) & (df["pop"] > 0)]
    if len(df) < before:
        print(f"  [{year}] dropped {before - len(df)} countries with a non-positive MLD or population")

    missing_region = sorted(set(df.index) - set(regions.index))
    if missing_region:
        print(f"  [{year}] no region for {len(missing_region)}: {missing_region[:5]} -> 'Other'")
    return df.assign(region=df.index.map(regions).fillna("Other"),
                     ratio=df.wid / df.pip).sort_index()


def build_file(frames, stats_by_concept, tax_word, title):
    region_order = sorted(set().union(*(set(f.region) for f in frames.values())))
    ridx = {r: i for i, r in enumerate(region_order)}

    # Same three views as the means scatter, each fitted on its own plotted
    # variables rather than transformed from another's coefficients.
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
        years_out[str(y)] = {
            "n_countries": int(len(df)),
            "fits": fits,
            "ratio_summary": ratio_stats(df),
            # Every concept's ratio stats, in BOTH files, so one slide can show a
            # pre-tax/post-tax summary table whichever file it is pointed at.
            "ratio_stats": stats_by_concept[y],
            # [country, region index, PIP within-MLD, WID within-MLD, population]
            "points": [[c, ridx[r["region"]], round(r.pip, 4), round(r.wid, 4), int(r["pop"])]
                       for c, r in df.iterrows()],
        }
        st = ratio_stats(df)
        print(f"  [{y}] {len(df)} countries | WID {tax_word} / PIP within-MLD: "
              f"mean {st['mean']:.2f}x (pop-wtd {st['pop_weighted_mean']:.2f}x), "
              f"median {st['median']:.2f}x (pop-wtd {st['pop_weighted_median']:.2f}x), "
              f"range {st['min']:.2f}-{st['max']:.2f}x")
        for v in VIEWS:
            print(f"        {v:<7} slope {fits[v]['unweighted']['slope']:+.3f} "
                  f"(R2 {fits[v]['unweighted']['r2']:.3f}) | weighted "
                  f"{fits[v]['weighted']['slope']:+.3f} (R2 {fits[v]['weighted']['r2']:.3f})")

    return {
        "meta": {
            "title": title,
            "x_label": "Within-country MLD — World Bank PIP (disposable income or consumption, per capita)",
            "y_label": f"Within-country MLD — WID ({tax_word} national income, per capita)",
            "ratio_label": f"WID ({tax_word}) ÷ PIP, within-country MLD",
            "share_label": f"PIP within-country MLD as a share of WID ({tax_word})",
            "x_tip_label": "PIP within-MLD",
            "y_tip_label": f"WID within-MLD ({tax_word})",
            "years": [str(y) for y in DECK_YEARS],
            "default_year": str(es.DISPLAY_YEAR),
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
            # Kept short: the component prints this at the end of a one-line
            # source note, which clips at the edge of its 1000px viewBox.
            "units": "Mean log deviation (GE(0)), within each country.",
            "notes": [
                "These are the SAME country within-MLDs the ETL aggregates into the "
                "global within component of the bridging figure: that bar is the "
                "population-weighted mean of these values. Nothing is recomputed here.",
                "Bubble area is proportional to population, on the ETL's single "
                "population yardstick (OWID population for per-capita series) — the "
                "same denominator both axes use. Asserted in the script.",
                "Both WID concepts are published as separate files with identical "
                "axes, because within-country inequality differs sharply before and "
                "after tax (unlike the country means, equal by DINA construction).",
                "Zeros are retained upstream in the harmonized distributions; WID "
                "zero-income bins enter the MLD at $0.01/day, as everywhere else in "
                "the deck. Countries with a non-positive MLD or population are "
                "dropped here because both axes are logarithmic.",
                "1990 is the first year the ETL covers. Survey coverage that far back "
                "is thin: many country-years are interpolated or extrapolated by the "
                "source, on both sides.",
                "Each view is regressed on its own plotted variables, unweighted and "
                "weighted by population.",
            ],
            "generated_by": "data/scripts/29_fig_mld_scatter.py",
        },
        "regions": region_order,
        "years": years_out,
    }


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    dec = es.load("inequality_decomposition_by_country")   # deck series names already
    regions = es.load("treemap_regions").set_index("country")["region"]

    # Both concepts are built first: each file carries every concept's ratio
    # stats, so the summary table does not depend on which file a slide loads.
    frames_by_concept = {
        tax_word: {y: build_year(dec, regions, wid_series, y) for y in DECK_YEARS}
        for _, wid_series, tax_word, _ in WID_VARIANTS
    }
    stats_by_concept = {
        y: {tax_word: ratio_stats(frames[y]) for tax_word, frames in frames_by_concept.items()}
        for y in DECK_YEARS
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, wid_series, tax_word, title in WID_VARIANTS:
        print(f"{wid_series} on the y axis")
        out = build_file(frames_by_concept[tax_word], stats_by_concept, tax_word, title)
        path = FIGURES_DIR / f"fig_mld_scatter{suffix}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
        print(f"Saved: {path} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
