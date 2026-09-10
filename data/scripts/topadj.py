"""
topadj.py — THE definition of the top-adjusted PIP series ("PIP_topadj").

This module is the single place the method lives, so no two figures can drift
apart methodologically.

THE METHOD (since 2026-09-09): the top 1%, two ways
---------------------------------------------------
Both say "WID is right about the top 1%"; they differ only in what they assume
went wrong with the survey. See the block comment above build_top1() for the
algebra, the gate, and why only one of them fits the deck's percentile grid.

The BASE series is a parameter. The deck applies the top adjustment ON TOP of
the consumption->income adjustment (base = "PIP_consinc", built by consinc.py)
— an additional step in the PIP-side chain, not an alternative to it. The
scenario grid in the deck also prices it against raw PIP.

WHAT THIS REPLACED (2026-09-09)
-------------------------------
Until this date the deck grafted WID's SHAPE onto PIP above a switchable anchor
(P95 / P98 / P99), with share matching as a second method at the same anchors —
a 2 x 3 cross. Joe dropped both the graft and the anchor dimension: the exercise
is now about the top 1% alone, and about under-reporting versus
under-representation rather than shape versus share. build_from_bins() and
build_share_matched_from_bins() are gone.

build_pip_topadj() and anchor_bin_label() BELOW ARE NOT PART OF THAT. They are
the old local-pipeline graft, kept because scripts 10, 11, 13, 14 and
scenarios.py — the reference implementation the project deliberately preserves —
still import them. Nothing the deck displays goes through them.
"""

import numpy as np
import pandas as pd

DEFAULT_SPLICE_PERCENTILE = 99
WID_SHAPE_SOURCE = "WID_posttax_per_capita"


# ---------------------------------------------------------------------------
# THE TOP-1% METHODS (2026-09-09). Two ways of saying "WID is right about the
# top 1%", differing ONLY in what they assume went wrong with the survey:
#
#   MATCH  — UNDER-REPORTING. PIP samples the right people; the top 1% simply
#            reports too little. So PIP's own top 1% is kept in place and
#            rescaled until its income share equals WID's.
#
#   APPEND — UNDER-REPRESENTATION. The very rich are missing from the sample
#            altogether (Anand & Segal 2015, Handbook of Income Distribution
#            vol 2A ch. 11, p. 954). So the WHOLE survey is re-read as the
#            bottom 99% — every weight multiplied by 0.99 — and a new top
#            percentile is appended with WID's income share. PIP's own top 1%
#            is not discarded; it is re-ranked into the 98th-99th percentile.
#
# Both aggregate the top 1% to a SINGLE bin on both sides, so they differ in
# exactly one thing and nothing else. Both share the closed form
#
#       Y' = A / (1 - S)
#
# where S is WID's top-1% share of WID's own total and A is the income of the
# retained block — which is the only thing that differs:
#
#       match:   A = income of PIP's bottom 99%          = Y_s (1 - s_P)
#       append:  A = income of the WHOLE survey x 0.99   = 0.99 Y_s
#
# so append always lifts the mean further, by roughly 0.99/(1 - s_P).
#
# THE GATE. Neither is applied to a country whose own top-1% share already
# exceeds WID's: "assume WID is right about the top" would there mean revising
# the top DOWN, which is not what either story claims. Those countries pass
# through untouched, which makes the output RAGGED (100 or 101 bins where
# adjusted, the grid where not) — see etl_mld.decompose(expect_bins=None).
# Without the gate the append join inverts in exactly the countries where
#       s_P > 0.99 S / (1 - S)
# — the gate is slightly stricter than that, and simpler to state.
TOP1_START = 0.99          # the top 1% is every bin at or above this rank


def top1_shares(bins, base_series, shape_series=WID_SHAPE_SOURCE):
    """Per country: PIP's and WID's top-1% share of their own totals, and the gate.

    The gate is `wid > pip`: only correct the top upward.
    """
    rows = []
    for c, g in bins[bins["series"] == base_series].groupby("country", observed=True):
        top = g[g["p_low"] >= TOP1_START - 1e-9]
        s_p = float((top["pop"] * top["avg"]).sum() / (g["pop"] * g["avg"]).sum())
        sh = bins[(bins["series"] == shape_series) & (bins["country"] == c)]
        wtop = sh[sh["p_low"] >= TOP1_START - 1e-9]
        s_w = float((wtop["pop"] * wtop["avg"]).sum() / (sh["pop"] * sh["avg"]).sum())
        rows.append((c, s_p, s_w, s_w > s_p))
    return pd.DataFrame(rows, columns=["country", "pip_share", "wid_share",
                                       "adjust"]).set_index("country")


def _aggregate_top1(g):
    """One country's bins with the top 1% collapsed to a single 1%-wide bin."""
    g = g.sort_values("p_low")
    m = g["p_low"].to_numpy(float) >= TOP1_START - 1e-9
    top, rest = g[m], g[~m].copy()
    one = top.iloc[[0]].copy()
    one["avg"] = float(np.average(top["avg"], weights=top["pop"]))
    one["pop"] = float(top["pop"].sum())
    one["p_low"], one["p_high"] = float(top["p_low"].min()), float(top["p_high"].max())
    one["percentile"] = "p99p100"
    return pd.concat([rest, one], ignore_index=True).sort_values("p_low")


def build_top1(bins, method, base_series="PIP_consinc", shape_series=WID_SHAPE_SOURCE,
               out_series="PIP_top1", gate=True, grid=False):
    """MATCH or APPEND, at the top 1%, with the gate. See the block comment above.

    Returns a bins frame; countries that fail the gate are passed through with
    their ORIGINAL bins.

    grid=True (MATCH only) writes the adjusted top back as the base series' OWN
    ten 0.1% bins, all at the matched value, instead of one aggregated 1% bin.
    That is the SAME distribution — ten equal bins and one bin of the same total
    width and value are indistinguishable to any inequality measure — but it
    keeps the deck's 109-bin grid, so every figure downstream keeps working.
    APPEND cannot do this: it re-reads the survey as the bottom 99%, so its
    bins land on ranks the grid does not have, and putting it back on the grid
    would need an interpolation this project has so far avoided. Append is
    therefore RAGGED (101 bins where adjusted, 109 where not) and belongs in the
    scenario comparisons rather than in the bridging chain — see
    etl_mld.decompose(expect_bins=None).
    """
    assert method in ("match", "append"), method
    assert not (grid and method == "append"), \
        "append is ragged by construction — call it without grid=True"
    g8 = top1_shares(bins, base_series, shape_series)
    out = []
    for c, g in bins[bins["series"] == base_series].groupby("country", observed=True):
        g = g.sort_values("p_low")
        if gate and not bool(g8.loc[c, "adjust"]):
            pt = g.copy()
            pt["series"] = out_series
            out.append(pt)
            continue
        S = float(g8.loc[c, "wid_share"])
        assert S < 1, f"WID top share >= 1 for {c}"
        agg = _aggregate_top1(g)
        pop_total = float(agg["pop"].sum())
        if method == "match":
            # PIP's own top 1% stays where it is; only its level changes.
            below = agg[agg["p_low"] < TOP1_START - 1e-9].copy()
            A = float((below["pop"] * below["avg"]).sum())
            total = A / (1.0 - S)
            if grid:
                # the base series' own top bins, all at the matched value
                top = g[g["p_low"] >= TOP1_START - 1e-9].copy()
                top["avg"] = S * total / float(top["pop"].sum())
                below = g[g["p_low"] < TOP1_START - 1e-9].copy()
            else:
                top = agg[agg["p_low"] >= TOP1_START - 1e-9].copy()
                top["avg"] = S * total / float(top["pop"].iloc[0])
            frame = pd.concat([below, top], ignore_index=True)
        else:
            # The survey IS the bottom 99%; a new top percentile is appended.
            keep = agg.copy()
            keep["pop"] = keep["pop"].to_numpy(float) * TOP1_START
            keep["p_low"] = keep["p_low"].to_numpy(float) * TOP1_START
            keep["p_high"] = keep["p_high"].to_numpy(float) * TOP1_START
            # Every retained bin now sits at a rank its old label no longer
            # describes. RELABEL, so that a label lookup written for the grid
            # (`by_pct["p90p91"]`) raises instead of quietly returning a bin
            # that is nearly a whole percentile off — the error was 4-6% at P90.
            # Read this series by rank window; see 21_..._from_etl.rank_window.
            keep["percentile"] = [f"p{lo * 100:.4g}p{hi * 100:.4g}" for lo, hi
                                  in zip(keep["p_low"], keep["p_high"])]
            A = float((keep["pop"] * keep["avg"]).sum())
            total = A / (1.0 - S)
            add = keep.iloc[[-1]].copy()
            add["pop"] = (1.0 - TOP1_START) * pop_total
            add["avg"] = S * total / float(add["pop"].iloc[0])
            add["p_low"], add["p_high"] = TOP1_START, 1.0
            add["percentile"] = "p99p100"
            frame = pd.concat([keep, add], ignore_index=True)
        frame["series"] = out_series
        out.append(frame)
    return pd.concat(out, ignore_index=True)


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
