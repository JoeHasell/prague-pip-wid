"""
11_fig_topadj_explainer.py — data for the deck figure "fig-topadj-explainer".

THE FIGURE (rendered by components/fig-topadj-explainer.js)
------------------------------------------------------------
An interactive explainer of the top-adjustment step, showing the full
PIP-side chain for a selectable country (default Indonesia):

    consumption (observed, where applicable)
      -> income basis (the consumption->income adjustment, consinc.py)
        -> top-adjusted (WID post-tax top shape grafted above P95, topadj.py)

For income-based countries the first stage doesn't exist (their income
series IS the observed one) — the chart then shows two lines.

The methods are defined once each in consinc.py and topadj.py; this script
just evaluates them for every country present in both PIP and the WID shape
source, with the SAME parameters as the bridging figure
(10_fig_raw_comparison.py): splice P95, base = PIP_consinc.

OUTPUT (data/figures/fig_topadj_explainer.json), kept compact:
  meta        splice/anchor info, default country
  percentiles the 109 bin labels and midpoints, once
  countries   { name: { "pip":  [109 bin averages]            — observed PIP,
                        "consinc": [109]                       — only for
                            consumption countries (else identical to pip),
                        "adj":  [values for bins ABOVE the anchor only] } }

Run:  python data/scripts/11_fig_topadj_explainer.py
"""

import json
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, PROCESSED_DIR
from config import RAW_PIP_DIR, DAILY_TO_MONTHLY
from topadj import build_pip_topadj, anchor_bin_label, WID_SHAPE_SOURCE
from consinc import build_pip_consinc

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_topadj_explainer.json"

SPLICE_PERCENTILE = 95   # keep in sync with 10_fig_raw_comparison.py


def sig4(x):
    # Displayed values are PER MONTH (config.DAILY_TO_MONTHLY); the pipeline
    # is daily internally.
    return float(f"{x * DAILY_TO_MONTHLY:.4g}")


# Superseded by the ETL pipeline — see legacy_guard.py.
from legacy_guard import require_ack


def main():
    require_ack(
        script='11_fig_topadj_explainer.py',
        figures=['fig_topadj_explainer.json'],
        replaced_by='23_fig_explainers_from_etl.py',
    )
    h = pd.read_csv(HARMONIZED_FILE)
    model = pd.read_csv(PROCESSED_DIR / "consinc_model.csv")
    welfare = pd.read_csv(RAW_PIP_DIR / "pip_welfare_types.csv")
    wtype = dict(zip(welfare["country"], welfare["welfare_type"]))

    # Countries: need both PIP (for consinc) and the WID shape source
    pip_c = set(h.loc[h.source == "PIP", "country"])
    wid_c = set(h.loc[h.source == WID_SHAPE_SOURCE, "country"])
    countries = sorted(pip_c & wid_c)

    consinc, rep = build_pip_consinc(h, model, welfare, countries=countries)
    h2 = pd.concat([h, consinc], ignore_index=True)
    adj_all = build_pip_topadj(h2, countries=countries,
                               splice_percentile=SPLICE_PERCENTILE,
                               base_source="PIP_consinc")
    print(f"{len(countries)} countries "
          f"({rep['consumption_adjusted']} consumption-based, "
          f"{rep['income_passthrough']} income-based)")

    anchor = anchor_bin_label(SPLICE_PERCENTILE)
    ref = h[(h.source == "PIP") & (h.country == countries[0])].sort_values("p_low")
    labels = ref["percentile"].tolist()
    mids = ((ref["p_low"] + ref["p_high"]) / 2 * 100).round(3).tolist()
    anchor_idx = labels.index(anchor)

    data = {}
    for c in countries:
        pip = h[(h.source == "PIP") & (h.country == c)].sort_values("p_low")["average"]
        ci = consinc[consinc.country == c].sort_values("p_low")["average"]
        adj = adj_all[adj_all.country == c].sort_values("p_low")["average"]
        entry = {"pip": [sig4(v) for v in pip]}
        if wtype.get(c) == "consumption":
            entry["consinc"] = [sig4(v) for v in ci]
        # the adjusted series equals consinc up to the anchor by construction
        assert [sig4(v) for v in adj.iloc[:anchor_idx + 1]] == [sig4(v) for v in ci.iloc[:anchor_idx + 1]], \
            f"adjusted series differs below the anchor for {c}"
        entry["adj"] = [sig4(v) for v in adj.iloc[anchor_idx + 1:]]
        data[c] = entry

    out = {
        "meta": {
            "title": "The top adjustment, applied on top of the income-basis adjustment",
            "splice_percentile": SPLICE_PERCENTILE,
            "anchor_bin": anchor,
            "anchor_index": anchor_idx,
            "shape_source": WID_SHAPE_SOURCE,
            "base_source": "PIP_consinc",
            "default_country": "Indonesia",
            "units": "international-$ per month (converted from daily at 365/12)",
            "notes": [
                "Chain: consumption (observed) -> income basis (consinc.py) "
                "-> top-adjusted above P95 (topadj.py).",
                "adj holds values only for bins above the anchor; below that "
                "the adjusted series equals the income-basis series.",
                "consinc present only for consumption-based countries; for "
                "income countries the income basis IS the observed PIP series.",
            ],
            "generated_by": "data/scripts/11_fig_topadj_explainer.py",
        },
        "percentiles": {"labels": labels, "mids": mids},
        "countries": data,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"Saved: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
