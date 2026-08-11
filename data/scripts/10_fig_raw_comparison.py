"""
10_fig_raw_comparison.py — data for the deck figure "fig-raw-comparison".

THE FIGURE (rendered by components/fig-raw-comparison.js)
----------------------------------------------------------
The raw, before-any-bridging comparison of WID and PIP for three countries
(United States, Indonesia, Nigeria):

  Row 1  Lollipops of P10 (bin p10p11), P90 (bin p90p91) and the country MEAN,
         income $/day on a shared log axis. WID pre-tax per adult on the left,
         PIP on the right.
  Row 2  Stacked bars of the MLD (mean log deviation) LEVEL decomposed into
         between-country and within-country components, computed on the FULL
         distributions of just these three countries — one bar per source.

ALL FIVE series in the harmonized dataset are computed and written to the
JSON; the component chooses which to show (and in what order) via its
`sources` prop. This is what lets the deck "build up" the comparison across
slides: the raw two-column slide and the bridging-steps slide share this one
script and one JSON:
  - WID_pretax_per_adult  : pre-tax national income, per adult (the raw headline)
  - WID_pretax_per_capita : bridging step — same income, per-capita basis
  - WID_posttax_per_adult : post-tax national income, per adult (not currently shown)
  - WID_posttax_per_capita: bridging step — post-tax, per capita
  - PIP                   : disposable income/consumption, per capita (the target)

METHOD NOTES
------------
All MLD decompositions go through data/scripts/mld.py, which bakes in the
two project-wide conventions (see its docstring for the formulas and the
full rationale):
  1. POPULATION WEIGHTS COME FROM WID for every series (incl. PIP), matched
     to each series' basis: adult populations for per-adult series, total
     populations for per-capita series. The sources' demographic
     disagreements never enter the comparison. A sensitivity line comparing
     against PIP weights is printed on each run.
  2. ZERO INCOMES are replaced with $0.01/day inside the MLD only.
The lollipop values (P10/P90/mean) are unaffected by either convention:
no zero bins at those points, and within a country the mean is invariant
to which source's population total is used.

INPUT   data/processed/pip_wid_harmonized_2023.csv
OUTPUT  data/figures/fig_raw_comparison.json   (fetched by the component)

Run:  python data/scripts/10_fig_raw_comparison.py
"""

import json
import numpy as np
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, DAILY_TO_MONTHLY

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_raw_comparison.json"

COUNTRIES = ["United States", "Indonesia", "Nigeria"]
SOURCES = {
    "WID_pretax_per_adult": "WID (pre-tax national income, per adult)",
    "WID_pretax_per_capita": "WID (pre-tax national income, per capita)",
    "WID_posttax_per_adult": "WID (post-tax national income, per adult)",
    "WID_posttax_per_capita": "WID (post-tax national income, per capita)",
    "PIP": "PIP (disposable income or consumption, per capita)",
    "PIP_topadj": "PIP on an income basis, top-adjusted (WID post-tax shape grafted above the splice bin, applied ON TOP of the consumption->income adjustment)",
    "WID_posttax_rescaled": "WID post-tax, rescaled to the ADJUSTED PIP country means (shape from WID, level from PIP_topadj — the far end of the PIP-side chain — so the bridge meets in the middle)",
    "PIP_consinc": "PIP adjusted to an income basis (consumption countries mapped via the dual-country regression)",
}
ZERO_REPLACEMENT = 0.01  # $/day, applied ONLY inside the MLD calculation

# MLD decomposition with the project-wide conventions (WID population
# weights, zero replacement) — defined once in mld.py.
from mld import mld_decomposition

# ---------------------------------------------------------------------------
# The top-adjusted PIP series ("PIP_topadj")
# ---------------------------------------------------------------------------
# The method (graft WID's post-tax top-tail shape onto PIP above a splice
# point) is defined ONCE, in topadj.py — see that module's docstring for the
# formula and the splice convention. This script only chooses the parameter.
from topadj import build_pip_topadj, anchor_bin_label, WID_SHAPE_SOURCE
# The mean-rescaled WID series (WID post-tax shapes, ADJUSTED-PIP means:
# mean_source="PIP_topadj") is likewise defined once, in rescale.py.
from rescale import build_wid_rescaled
# The income-basis-adjusted PIP series is defined in consinc.py, using the
# regression + welfare lookup produced by 04_fit_consinc.py.
from consinc import build_pip_consinc
from config import PROCESSED_DIR, RAW_PIP_DIR

SPLICE_PERCENTILE = 95            # anchor bin p94p95; first adjusted bin p95p96


def main():
    h = pd.read_csv(HARMONIZED_FILE)
    # Append the derived series so they flow through the same lollipop/MLD
    # computations as every other source.
    consinc_model = pd.read_csv(PROCESSED_DIR / "consinc_model.csv")
    welfare = pd.read_csv(RAW_PIP_DIR / "pip_welfare_types.csv")
    consinc, rep = build_pip_consinc(h, consinc_model, welfare, countries=COUNTRIES)
    print(f"PIP_consinc: {rep['consumption_adjusted']} adjusted, "
          f"{rep['income_passthrough']} pass-through, "
          f"not in lookup: {rep['not_in_lookup'] or 'none'}")
    # The PIP-side chain: consinc first, then the top adjustment ON TOP of it
    h = pd.concat([h, consinc], ignore_index=True)
    h = pd.concat([h, build_pip_topadj(h, countries=COUNTRIES,
                                       splice_percentile=SPLICE_PERCENTILE,
                                       base_source="PIP_consinc")],
                  ignore_index=True)
    # The rescaled WID series takes its means from PIP_topadj (the far end
    # of the PIP-side chain), so it must be built AFTER topadj is appended.
    h = pd.concat([h, build_wid_rescaled(h, countries=COUNTRIES,
                                         mean_source="PIP_topadj")],
                  ignore_index=True)

    lollipop = []
    mld = []
    for source, label in SOURCES.items():
        d = h[(h.source == source) & (h.country.isin(COUNTRIES))].copy()
        assert d.groupby("country").size().eq(109).all(), f"missing bins for {source}"

        for c in COUNTRIES:
            g = d[d.country == c]
            # Displayed values are PER MONTH (config.DAILY_TO_MONTHLY); the
            # pipeline is daily internally.
            k = DAILY_TO_MONTHLY
            lollipop.append({
                "source": source,
                "country": c,
                "p10": float(g.loc[g.percentile == "p10p11", "average"].iloc[0]) * k,
                "p90": float(g.loc[g.percentile == "p90p91", "average"].iloc[0]) * k,
                "mean": float(np.average(g["average"], weights=g["pop"])) * k,
                # The extreme bins (optionally shown as hollow circles via the
                # component's `extremes` prop). NOTE: p0p1 can be exactly 0 in
                # WID series — the component pins those at the axis floor.
                "p0": float(g.loc[g.percentile == "p0p1", "average"].iloc[0]) * k,
                "p999": float(g.loc[g.percentile == "p99.9p100", "average"].iloc[0]) * k,
            })

        res = mld_decomposition(h, source, COUNTRIES,
                                 zero_replacement=ZERO_REPLACEMENT)
        res["source"] = source
        res["label"] = label
        mld.append(res)
        print(f"{source}: MLD total={res['total']:.3f}  "
              f"between={res['between']:.3f}  within={res['within']:.3f}  "
              f"(between share {res['between_share']:.1%}, "
              f"{res['zero_bins_replaced']} zero bins replaced)")

    # Weight-yardstick sensitivity (printed only, not plotted): how much the
    # headline PIP decomposition moves if PIP's own populations are used.
    alt = mld_decomposition(h, "PIP", COUNTRIES,
                            zero_replacement=ZERO_REPLACEMENT, weights="pip")
    base = next(m for m in mld if m["source"] == "PIP")
    print(f"\n[sensitivity] PIP between-share: {base['between_share']:.1%} "
          f"(WID weights, the convention) vs {alt['between_share']:.1%} "
          f"(PIP weights) — delta "
          f"{abs(base['between_share'] - alt['between_share']) * 100:.2f}pp")

    out = {
        "meta": {
            "title": "Raw comparison: WID vs PIP, three countries, 2023",
            "countries": COUNTRIES,
            "sources": SOURCES,
            "year": 2023,
            "units": "international-$ PER MONTH (PIP: 2021 PPPs; WID: 2023 "
                     "PPPs); converted from daily values at 365/12",
            "zero_replacement_usd_per_day": ZERO_REPLACEMENT,
            "topadj_splice_percentile": SPLICE_PERCENTILE,
            "topadj_anchor_bin": anchor_bin_label(SPLICE_PERCENTILE),
            "topadj_shape_source": WID_SHAPE_SOURCE,
            "topadj_base_source": "PIP_consinc",
            "rescale_mean_source": "PIP_topadj",
            "notes": [
                "P10/P90 are the bin averages of p10p11 / p90p91.",
                "MLD computed on the full 109-bin distributions of the three "
                "countries only; zeros replaced with $0.01/day for the MLD only.",
                "MLD weighting convention: ALL series are weighted by WID's "
                "demography, matched to each series' basis (adults for "
                "per-adult, total population otherwise) — see "
                "data/scripts/mld.py.",
            ],
            "generated_by": "data/scripts/10_fig_raw_comparison.py",
        },
        "lollipop": lollipop,
        "mld": mld,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
