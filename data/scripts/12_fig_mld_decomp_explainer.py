"""
12_fig_mld_decomp_explainer.py — data for the deck figure "fig-mld-decomp".

THE FIGURE (rendered by components/fig-mld-decomp.js)
------------------------------------------------------
A pedagogical breakdown of the MLD decomposition for the three highlight
countries, using the slide-12 pair of series (WID pre-tax per adult vs PIP).

The intuition the figure carries: on a LOG income axis, each person's
log-gap to the overall mean is a visible distance, and it splits exactly:

    ln(mu / x_i) = ln(mu / mu_c) + ln(mu_c / x_i)
                   [between gap]   [within gap]

Averaging over everyone (population-weighted) gives
    MLD = Between + Within.

So the figure shows, per source: each country's distribution as dots
(decile bin averages) on a shared log axis, the country means, the overall
mean, annotated example gaps, and the resulting between/within stacked bar.

All means/decompositions follow the project conventions in mld.py
(WID demography matched to the series' basis; zeros -> $0.01 in the MLD).

INPUT   data/processed/pip_wid_harmonized_2023.csv
OUTPUT  data/figures/fig_mld_decomp_explainer.json

Run:  python data/scripts/12_fig_mld_decomp_explainer.py
"""

import json
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, DAILY_TO_MONTHLY
from mld import mld_decomposition

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_mld_decomp_explainer.json"

COUNTRIES = ["United States", "Indonesia", "Nigeria"]
SOURCES = {
    "WID_pretax_per_adult": "WID — pre-tax national income, per adult",
    "PIP": "PIP — disposable income or consumption, per capita",
}
# Decile bins shown as "people" (p10p11 ... p90p91: no zero bins up here)
DECILE_BINS = [f"p{d}p{d + 1}" for d in range(10, 100, 10)]


def main():
    h = pd.read_csv(HARMONIZED_FILE)

    out_sources = []
    for source, label in SOURCES.items():
        res = mld_decomposition(h, source, COUNTRIES)
        d = h[(h.source == source) & (h.country.isin(COUNTRIES))]

        total_pop = sum(c["pop"] for c in res["countries"])
        countries = []
        for cdet in res["countries"]:
            c = cdet["country"]
            g = d[d.country == c].set_index("percentile")["average"]
            # Money values are displayed PER MONTH (config.DAILY_TO_MONTHLY);
            # the pipeline is daily internally. The MLD terms are ratios of
            # incomes and thus unit-free — they are NOT converted.
            k = DAILY_TO_MONTHLY
            countries.append({
                "country": c,
                "mean": round(cdet["mean"] * k, 4),
                "within_mld": round(cdet["mld_within"], 4),
                "pop_share": round(cdet["pop"] / total_pop, 4),
                "pop": round(cdet["pop"]),
                "deciles": {b: round(float(g[b]) * k, 4) for b in DECILE_BINS},
            })

        out_sources.append({
            "source": source,
            "label": label,
            # what the weights count, per the basis-matched convention
            "weight_basis": "adults" if "per_adult" in source else "people",
            "mu": round(res["grand_mean"] * DAILY_TO_MONTHLY, 4),
            "between": round(res["between"], 4),
            "within": round(res["within"], 4),
            "total": round(res["total"], 4),
            "between_share": round(res["between_share"], 4),
            "countries": countries,
        })
        print(f"{source}: mu={res['grand_mean']:.1f}  between={res['between']:.3f}  "
              f"within={res['within']:.3f}  total={res['total']:.3f}")

    out = {
        "meta": {
            "title": "Anatomy of the MLD decomposition",
            "countries": COUNTRIES,
            "decile_bins": DECILE_BINS,
            "units": "international-$ per month (converted from daily at "
                     "365/12; MLD terms are unit-free and unconverted)",
            "notes": [
                "Dots are decile bin averages (p10p11 ... p90p91).",
                "Identity: ln(mu/x) = ln(mu/mu_c) + ln(mu_c/x); MLD is the "
                "population-weighted average of these gaps.",
                "Conventions (weights, zeros) as per data/scripts/mld.py.",
            ],
            "generated_by": "data/scripts/12_fig_mld_decomp_explainer.py",
        },
        "sources": out_sources,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
