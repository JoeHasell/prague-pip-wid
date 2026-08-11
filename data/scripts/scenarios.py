"""
scenarios.py — the seven displayed income scenarios, defined once.

The Q2 bridging charts (10_fig_raw_comparison.py, 14_fig_bridging_all.py)
and the Q3 top-of-the-distribution figures (15_fig_top_thresholds.py,
16_fig_top1_treemap.py) all work with the SAME seven series in the SAME
order. This module holds that list plus the two helpers those scripts share:

  common_sample(h)      the countries present in PIP and every WID variant
                        (the "211-country common sample")
  append_derived(h, countries)
                        appends the three derived series with the deck's
                        parameters, in the required order:
                          PIP_consinc  (consinc.py)
                          PIP_topadj   (topadj.py, splice P95, base consinc)
                          WID_posttax_rescaled (rescale.py, means from topadj)

Parameters here MUST stay in sync with 10_fig_raw_comparison.py — the deck's
methodological choices are documented in the method modules themselves
(consinc.py, topadj.py, rescale.py, mld.py).
"""

import pandas as pd

from config import PROCESSED_DIR, RAW_PIP_DIR
from topadj import build_pip_topadj
from rescale import build_wid_rescaled
from consinc import build_pip_consinc

SPLICE_PERCENTILE = 95   # keep in sync with 10_fig_raw_comparison.py

# The seven scenarios shown in the deck, in bridging order (WID side ->
# meeting point -> PIP side). label: for dropdowns/titles; short: two-line
# column headers matching fig-raw-comparison.js.
DISPLAY_SCENARIOS = [
    {"source": "WID_pretax_per_adult",
     "label": "WID pre-tax national income, per adult",
     "short": ["WID pre-tax", "per adult"], "basis": "adult"},
    {"source": "WID_pretax_per_capita",
     "label": "WID pre-tax national income, per capita",
     "short": ["WID pre-tax", "per capita"], "basis": "total"},
    {"source": "WID_posttax_per_capita",
     "label": "WID post-tax national income, per capita",
     "short": ["WID post-tax", "per capita"], "basis": "total"},
    {"source": "WID_posttax_rescaled",
     "label": "WID post-tax, rescaled to adjusted PIP means",
     "short": ["WID post-tax", "at adjusted PIP means"], "basis": "total"},
    {"source": "PIP_topadj",
     "label": "PIP, income basis, top-adjusted",
     "short": ["PIP top-adjusted", "per capita"], "basis": "total"},
    {"source": "PIP_consinc",
     "label": "PIP, adjusted to an income basis",
     "short": ["PIP cons→income", "per capita"], "basis": "total"},
    {"source": "PIP",
     "label": "PIP, disposable income or consumption",
     "short": ["PIP", "per capita"], "basis": "total"},
]

RAW_NEEDED = ["PIP", "WID_pretax_per_adult", "WID_pretax_per_capita",
              "WID_posttax_per_adult", "WID_posttax_per_capita"]


def common_sample(h):
    """Countries present in PIP and every WID variant used by the deck."""
    sets = [set(h.loc[h.source == s, "country"]) for s in RAW_NEEDED]
    return sorted(set.intersection(*sets))


def append_derived(h, countries):
    """Append PIP_consinc, PIP_topadj and WID_posttax_rescaled (in that
    order — topadj needs consinc rows, rescaled needs topadj rows) with the
    deck's parameters. Returns (h_extended, consinc_report)."""
    model = pd.read_csv(PROCESSED_DIR / "consinc_model.csv")
    welfare = pd.read_csv(RAW_PIP_DIR / "pip_welfare_types.csv")
    consinc, rep = build_pip_consinc(h, model, welfare, countries=countries)
    h = pd.concat([h, consinc], ignore_index=True)
    h = pd.concat([h, build_pip_topadj(h, countries=countries,
                                       splice_percentile=SPLICE_PERCENTILE,
                                       base_source="PIP_consinc")],
                  ignore_index=True)
    h = pd.concat([h, build_wid_rescaled(h, countries=countries,
                                         mean_source="PIP_topadj")],
                  ignore_index=True)
    return h, rep
