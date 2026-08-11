"""
topadj.py — THE definition of the top-adjusted PIP series ("PIP_topadj").

This module is the single place the method lives; both the comparison figure
(10_fig_raw_comparison.py) and the explainer figure (11_fig_topadj_explainer.py)
import from here, so the two figures can never drift apart methodologically.

THE METHOD
----------
Below the splice point, the series IS the base series. From the splice point
upward, the top of the distribution is rebuilt with the SHAPE of the WID
post-tax (national income, diinc) distribution, anchored at the base
series' own level:

    adj(Py) = base(Px) * WID(Py) / WID(Px)      for bins above the anchor
    adj(Py) = base(Py)                          for the anchor bin and below

The BASE series is a parameter. As of 2026-08-11 the deck applies the top
adjustment ON TOP of the consumption->income adjustment (base_source =
"PIP_consinc", built by consinc.py) — it is an additional step in the
PIP-side chain, not an alternative to it.

CONVENTION (per Joe): the splice parameter names a percentile boundary.
splice_percentile = 99 ("Px = P99") means the ANCHOR bin is the bin just
below the boundary — p98p99 — and p99p99.1 is the FIRST bin whose value
differs. For splice_percentile = 95, the anchor is p94p95 and p95p96 is the
first adjusted bin.

Notes:
  - The anchor bin keeps its PIP value (ratio = 1 there): continuous splice.
  - The WID ratio is basis-invariant (per-adult vs per-capita cancels), so
    WID_posttax_per_capita is used but the choice does not matter.
  - The graft raises the country mean (WID's top tail is fatter than PIP's);
    means and income shares must be recomputed from the adjusted values —
    build_pip_topadj() recomputes the share column.
"""

import numpy as np
import pandas as pd

DEFAULT_SPLICE_PERCENTILE = 99
WID_SHAPE_SOURCE = "WID_posttax_per_capita"


def anchor_bin_label(splice_percentile):
    """The anchor bin for a splice percentile: P99 -> 'p98p99'."""
    return f"p{splice_percentile - 1}p{splice_percentile}"


def build_pip_topadj(h, countries=None, splice_percentile=DEFAULT_SPLICE_PERCENTILE,
                     base_source="PIP"):
    """Build the top-adjusted series from the harmonized dataset.

    Args:
        h: the harmonized DataFrame (columns incl. source, country,
           percentile, p_low, p_high, pop, average, share). Must already
           contain `base_source` rows (e.g. append the consinc series first).
        countries: list of country names, or None for every country present
           in BOTH the base source and the WID shape source.
        splice_percentile: see module docstring.
        base_source: the series the top is grafted onto ("PIP_consinc" in
           the deck's chain; "PIP" for the raw variant).

    Returns a DataFrame shaped like the harmonized file with
    source = 'PIP_topadj'.
    """
    anchor = anchor_bin_label(splice_percentile)

    if countries is None:
        pip_c = set(h.loc[h.source == base_source, "country"])
        wid_c = set(h.loc[h.source == WID_SHAPE_SOURCE, "country"])
        countries = sorted(pip_c & wid_c)

    out = []
    for c in countries:
        pip = h[(h.source == base_source) & (h.country == c)].sort_values("p_low").copy()
        wid = h[(h.source == WID_SHAPE_SOURCE) & (h.country == c)].sort_values("p_low")
        assert len(pip) == 109 and len(wid) == 109, f"missing bins for {c}"

        wid_avg = wid.set_index("percentile")["average"]
        anchor_p_low = float(pip.loc[pip.percentile == anchor, "p_low"].iloc[0])
        pip_at_anchor = float(pip.loc[pip.percentile == anchor, "average"].iloc[0])
        wid_at_anchor = float(wid_avg[anchor])
        assert wid_at_anchor > 0, f"WID anchor-bin value is zero for {c}"

        # Bins strictly above the anchor get WID's shape; the anchor bin and
        # everything below keep their PIP values.
        above = pip["p_low"] > anchor_p_low
        ratio = pip["percentile"].map(wid_avg) / wid_at_anchor
        pip["average"] = np.where(above, pip_at_anchor * ratio, pip["average"])

        # Sanity: monotone from the anchor up (WID's top is monotone, so a
        # violation means bins were misaligned).
        adj = pip.loc[pip["p_low"] >= anchor_p_low, "average"].to_numpy()
        assert (np.diff(adj) >= 0).all(), f"non-monotone top after graft for {c}"

        # Recompute income shares from the adjusted values
        pip["share"] = (pip["average"] * pip["pop"]) / (pip["average"] * pip["pop"]).sum()
        pip["source"] = "PIP_topadj"
        out.append(pip)
    return pd.concat(out, ignore_index=True)
