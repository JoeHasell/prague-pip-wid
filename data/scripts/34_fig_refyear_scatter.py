"""
34_fig_refyear_scatter.py — year-against-year inequality scatters with SELECTABLE years,
for the adjusted PIP series and WID.

    data/figures/fig_refyear_scatter.json  <- refyear-scatter, refyear-change-scatter
                                              (components/fig-refyear-scatter.js)

WHAT IT SHIPS
-------------
The reference-year dataset (33_reference_year_indicators.py) in a shape the
component can pair on the fly: for each series and country, one slot per
reference year 1990-2024 holding the survey year that was actually used, its
welfare concept and the four measures. The component then draws, for any two
years the viewer picks, a country's inequality in year A against year B (one
panel for a PIP series, one for a WID series) or the change in PIP against the
change in WID — applying the same rules refyears.pair() applies: a PIP pair
must be the same welfare concept on both ends, and the two survey years must
differ (one survey serves up to eleven reference years).

This is the ineq-trend figure (25_, fixed at 1993 vs 2019 on PIP's PUBLISHED
measures) generalised: any years, and PIP as published, on an income basis, or
with WID's top 1% appended — all from the bins, all on the deck's grid.

Values are rounded (Gini 4 dp, shares 2 dp, Palma 3 dp) and nulls mark
reference years with no survey within the window. Regions are PIP's old
seven-region scheme, as on the other scatters.

Run:  python data/scripts/34_fig_refyear_scatter.py
"""

import json
from pathlib import Path

import pandas as pd

import etl_source as es
import refyears

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
OUT_FILE = FIGURES_DIR / "fig_refyear_scatter.json"
IN_FILE = Path(__file__).resolve().parents[1] / "processed" / "reference_year_indicators.csv"

METRICS = {"gini": ("gini", 4), "top10": ("top10_share", 2), "top1": ("top1_share", 2), "palma": ("palma", 3)}
SERIES_LABELS = {
    "PIP": "PIP, as published",
    "PIP_consinc": "PIP on an income basis",
    "PIP_topadj": "PIP with WID's top 1% appended",
    "PIP_consinc_wb": "PIP on an income basis — Wollburg et al. (2023) inverse",
    "PIP_topadj_wb": "PIP with WID's top 1% appended — on the Wollburg et al. basis",
    "WID_pretax_per_capita": "WID pre-tax national income, per capita",
    "WID_posttax_per_capita": "WID post-tax national income, per capita",
}
WELFARE_CODE = {"income": "i", "consumption": "c"}


def main():
    print("Reading the reference-year dataset")
    ds = pd.read_csv(IN_FILE, keep_default_na=False, na_values=[""])
    years = sorted(int(y) for y in ds["ref_year"].unique())
    assert years == list(range(years[0], years[-1] + 1)), "reference years are not contiguous"
    index = {y: i for i, y in enumerate(years)}
    regions = es.load("country_regions").set_index("country")["region"]
    series_names = list(refyears.PIP_SIDE) + list(refyears.WID_SIDE)
    assert set(series_names) <= set(ds["series"].unique()), sorted(set(ds["series"].unique()))

    countries = sorted(ds["country"].unique())
    missing = [c for c in countries if c not in regions.index]
    assert not missing, f"no region for {missing[:5]}"

    out_series = {}
    for s in series_names:
        block = {}
        for c, g in ds[ds["series"] == s].groupby("country", sort=True):
            slots = {"y": [None] * len(years), "w": ["-"] * len(years)}
            for key in METRICS:
                slots[key] = [None] * len(years)
            for r in g.itertuples(index=False):
                i = index[int(r.ref_year)]
                slots["y"][i] = int(r.year)
                slots["w"][i] = WELFARE_CODE.get(r.welfare_type, "-") if isinstance(r.welfare_type, str) else "-"
                for key, (col, nd) in METRICS.items():
                    v = getattr(r, col)
                    slots[key][i] = None if pd.isna(v) else round(float(v), nd)
            slots["w"] = "".join(slots["w"])
            block[c] = slots
        out_series[s] = block
        n_slots = sum(sum(v is not None for v in b["y"]) for b in block.values())
        print(f"  {s:<24} {len(block):>3} countries, {n_slots:>5} country-reference-years")

    out = {
        "meta": {
            "title": "Inequality in one year against another",
            "years": years,
            "metrics": {"gini": "Gini", "top10": "Top 10% share", "top1": "Top 1% share", "palma": "Palma ratio"},
            "series": SERIES_LABELS,
            "pip_series": list(refyears.PIP_SIDE),
            "wid_series": list(refyears.WID_SIDE),
            "maximum_distance": 5,
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
            "generated_by": "34_fig_refyear_scatter.py",
            "units": "Gini 0-1; shares in percent of total income; Palma = top-10% share / bottom-40% share",
            "notes": [
                "Built from data/processed/reference_year_indicators.csv (33_reference_year_indicators.py): "
                "for each reference year, each country's nearest PIP SURVEY year within +-5 (ties to the "
                "earlier survey), and WID at the reference year itself. `y` is the survey year used for "
                "each reference year, `w` its welfare concept (i = income, c = consumption, - = n/a).",
                "All measures are computed from the harmonized bins on the deck's 100-percentile grid, "
                "for PIP as published, PIP on an income basis (WID's logit profile) and PIP with WID's "
                "top 1% appended (Anand-Segal), and for WID's two per-capita series.",
                "The two `_wb` PIP series are a parallel comparison chain: consumption countries put on "
                "PIP's own disposable-income basis by inverting Wollburg, Hallegatte & Mahler (2023)'s "
                "income->consumption model, inc = (con - g)^(1/a) with g = g0 + g1 ln(median income), the "
                "constants re-fitted at 2021 PPP on PIP's 88 dual country-years (35_fit_consinc_wb.py, "
                "data/processed/consinc_wb_fit.json), floored at $0.28/day, then the same top-1% append. "
                "The deck's baseline remains the WID profile; see consinc.py and data/README.md caveat 5.",
                "The component pairs two years with the rules of refyears.pair(): a PIP pair keeps only "
                "the same welfare concept on both ends, and the two survey years must differ. The ETL's "
                "inequality_comparison instead re-matches a country to a same-welfare pair further away, "
                "so its 1993/2019 country set differs slightly.",
                "Regions are PIP's old seven-region scheme (country_regions), as on the other scatters.",
            ],
        },
        "countries": {c: {"r": str(regions[c])} for c in countries},
        "series": out_series,
    }
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"\nSaved: {OUT_FILE.name} ({OUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
