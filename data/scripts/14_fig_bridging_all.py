"""
14_fig_bridging_all.py — data for the ALL-COUNTRIES bridging figure.

THE FIGURE (rendered by components/fig-raw-comparison.js, bars-only mode)
-------------------------------------------------------------------------
The same "bridging steps" stacked-bar chart as 10_fig_raw_comparison.py,
but with every MLD decomposition computed over the FULL common sample of
countries — every country present in both PIP and WID — rather than the
three example countries (US / Indonesia / Nigeria).

The component detects this dataset automatically: the `lollipop` array is
EMPTY, which switches fig-raw-comparison.js into "bars-only" mode (row 1
skipped, the MLD bars get the whole canvas). Everything else — the sources,
their order, the column headers — is driven by the same `sources` prop the
three-country slides use, so the two figures can never drift apart.

METHOD — identical to 10_fig_raw_comparison.py in every respect:
  - the PIP-side chain: consinc first (consinc.py), then the top adjustment
    ON TOP of it (topadj.py, splice P95, base = PIP_consinc);
  - the mean-rescaled WID series (rescale.py);
  - all decompositions via mld.py (WID demography matched to each series'
    basis; zeros -> $0.01/day inside the MLD only).
The ONLY difference is the country set. Countries missing from the PIP
welfare-type lookup pass through the consinc step unadjusted (counted and
printed below).

INPUT   data/processed/pip_wid_harmonized_2023.csv
OUTPUT  data/figures/fig_bridging_all.json   (fetched by the component)

Run:  python data/scripts/14_fig_bridging_all.py
"""

import json
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, PROCESSED_DIR, RAW_PIP_DIR, PPP_YEAR
from mld import mld_decomposition
from topadj import build_pip_topadj, anchor_bin_label, WID_SHAPE_SOURCE
from rescale import build_wid_rescaled
from consinc import build_pip_consinc

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_bridging_all.json"

# Keep labels and order in sync with 10_fig_raw_comparison.py
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
ZERO_REPLACEMENT = 0.01           # $/day, applied ONLY inside the MLD
SPLICE_PERCENTILE = 95            # anchor bin p94p95 — keep in sync with 10_fig


def main():
    h = pd.read_csv(HARMONIZED_FILE)

    # ------------------------------------------------------------------
    # The common sample: every country present in PIP AND all the WID
    # variants used (as raw series or as demography for the MLD weights).
    # ------------------------------------------------------------------
    raw_needed = ["PIP", "WID_pretax_per_adult", "WID_pretax_per_capita",
                  "WID_posttax_per_adult", "WID_posttax_per_capita"]
    sets = {s: set(h.loc[h.source == s, "country"]) for s in raw_needed}
    countries = sorted(set.intersection(*sets.values()))
    print(f"Common sample: {len(countries)} countries "
          f"({', '.join(f'{s}:{len(v)}' for s, v in sets.items())})")

    # ------------------------------------------------------------------
    # Derived series over the full common sample — same chain as 10_fig
    # ------------------------------------------------------------------
    consinc_model = pd.read_csv(PROCESSED_DIR / "consinc_model.csv")
    welfare = pd.read_csv(RAW_PIP_DIR / "pip_welfare_types.csv")
    consinc, rep = build_pip_consinc(h, consinc_model, welfare, countries=countries)
    print(f"PIP_consinc: {rep['consumption_adjusted']} adjusted, "
          f"{rep['income_passthrough']} pass-through, "
          f"not in lookup (passed through): {len(rep['not_in_lookup'])}")
    h = pd.concat([h, consinc], ignore_index=True)
    h = pd.concat([h, build_pip_topadj(h, countries=countries,
                                       splice_percentile=SPLICE_PERCENTILE,
                                       base_source="PIP_consinc")],
                  ignore_index=True)
    # The rescaled WID series takes its means from PIP_topadj (the far end
    # of the PIP-side chain), so it must be built AFTER topadj is appended.
    h = pd.concat([h, build_wid_rescaled(h, countries=countries,
                                         mean_source="PIP_topadj")],
                  ignore_index=True)

    # ------------------------------------------------------------------
    # MLD decomposition per source, all over the SAME country set
    # ------------------------------------------------------------------
    mld = []
    for source, label in SOURCES.items():
        res = mld_decomposition(h, source, countries,
                                zero_replacement=ZERO_REPLACEMENT)
        res.pop("countries")   # per-country details: too bulky at this scale
        res["source"] = source
        res["label"] = label
        mld.append(res)
        print(f"{source}: MLD total={res['total']:.3f}  "
              f"between={res['between']:.3f}  within={res['within']:.3f}  "
              f"(between share {res['between_share']:.1%}, "
              f"{res['zero_bins_replaced']} zero bins replaced)")

    # Weight-yardstick sensitivity (printed only): the headline PIP
    # decomposition under PIP's own populations.
    alt = mld_decomposition(h, "PIP", countries,
                            zero_replacement=ZERO_REPLACEMENT, weights="pip")
    base = next(m for m in mld if m["source"] == "PIP")
    print(f"\n[sensitivity] PIP between-share: {base['between_share']:.1%} "
          f"(WID weights, the convention) vs {alt['between_share']:.1%} "
          f"(PIP weights) — delta "
          f"{abs(base['between_share'] - alt['between_share']) * 100:.2f}pp")

    n = len(countries)
    out = {
        "meta": {
            "title": "The bridging steps, across the whole common sample",
            "row2_title": f"Global inequality across all {n} countries&rsquo; "
                          "populations combined — MLD level, decomposed",
            "scope_note": f"all {n} countries covered by both PIP and WID",
            "countries": countries,
            "n_countries": n,
            "sources": SOURCES,
            "year": 2023,
            "units": "MLD is unit-free; underlying incomes in international-$ "
                     f"(PIP: 2021 PPPs; WID: {PPP_YEAR} PPPs)",
            "zero_replacement_usd_per_day": ZERO_REPLACEMENT,
            "topadj_splice_percentile": SPLICE_PERCENTILE,
            "topadj_anchor_bin": anchor_bin_label(SPLICE_PERCENTILE),
            "topadj_shape_source": WID_SHAPE_SOURCE,
            "topadj_base_source": "PIP_consinc",
            "rescale_mean_source": "PIP_topadj",
            "notes": [
                "lollipop is deliberately EMPTY: that switches the component "
                "into bars-only mode (no per-country lollipop row).",
                "MLD computed on the full 109-bin distributions of every "
                "country in the common PIP-and-WID sample; zeros replaced "
                "with $0.01/day for the MLD only.",
                "MLD weighting convention: ALL series are weighted by WID's "
                "demography, matched to each series' basis (adults for "
                "per-adult, total population otherwise) — see "
                "data/scripts/mld.py.",
                "Countries absent from the PIP welfare-type lookup pass "
                "through the consumption->income step unadjusted.",
            ],
            "generated_by": "data/scripts/14_fig_bridging_all.py",
        },
        "lollipop": [],
        "mld": mld,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
