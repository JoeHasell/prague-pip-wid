"""
rescale.py — THE definition of the mean-rescaled WID series
("WID_posttax_rescaled").

THE METHOD
----------
Take the WID post-tax (national income, diinc) per-capita distribution and
rescale it, country by country, so that each country's mean equals its mean
in a chosen PIP-side series:

    factor(c)          = mean_source_mean(c) / WID_mean(c)
    rescaled(c, bin)   = WID_posttax_per_capita(c, bin) * factor(c)

WHICH MEANS? (decided 2026-08-11) The deck rescales to the means of the
TOP-ADJUSTED PIP series ("PIP_topadj", mean_source="PIP_topadj") — i.e. the
PIP series after BOTH PIP-side adjustments (consumption->income, then the
top adjustment). That way the bridging chart continues smoothly in both
directions: the WID-side ladder's last step (this series) has, by
construction, exactly the same country means — and therefore exactly the
same between component (see the weights note below) — as the PIP-side
ladder's last step (PIP_topadj). The remaining gap between the two columns
is purely a shape (within) difference. Rescaling to raw PIP means is the
mean_source="PIP" variant.

Each source's mean is computed with its own population weights (the mean
source's bin populations for itself; WID's bin total-populations for WID),
and the rescaled series KEEPS WID's bins and population weights. Multiplying
a distribution by a constant preserves its shape exactly — every relative
measure of within-country inequality (shares, ratios, within-country MLD) is
unchanged; only the level moves. So in a between/within decomposition, this
series isolates "WID's shapes with the target series' means".

Zero-income bins in WID remain zero after rescaling; as everywhere else,
zero handling is an analysis-stage decision.

KNOWN, ACCEPTED ARTIFACT (decided 2026-08-11): because the MLD stage replaces
zeros with an ABSOLUTE floor ($0.01/day) while this series rescales all other
incomes, the floor is relatively less extreme in countries scaled down (and
more extreme in countries scaled up). So this series' within-country MLD can
differ slightly from the base WID series' for countries with zero bins —
e.g. Nigeria (1 zero bin, factor 0.149 under mean_source="PIP"): within
0.814 -> 0.795, worth about -0.005 on the 3-country global within.
Rescaling is otherwise exactly within-preserving (countries without zero
bins match to machine precision). The alternative (transforming the floor
with the data, making within identical by construction) was considered and
rejected in favour of keeping the floor a single nominal constant everywhere.

NOTE ON WEIGHTS: MLD decompositions do not use this series' `pop` column —
per the project-wide convention, ALL MLD calculations weight countries by
WID's total populations (see mld.py). Under any single common yardstick this
series' between component equals the mean source's exactly, by construction.
"""

import pandas as pd

WID_BASE_SOURCE = "WID_posttax_per_capita"
DEFAULT_MEAN_SOURCE = "PIP"


def build_wid_rescaled(h, countries=None, mean_source=DEFAULT_MEAN_SOURCE):
    """Build the mean-rescaled WID series from the harmonized dataset.

    Args:
        h: the harmonized DataFrame. Must already contain `mean_source` rows
           (e.g. append the PIP_topadj series first when rescaling to it).
        countries: list of country names, or None for every country present
           in BOTH the mean source and the WID base source.
        mean_source: the series whose country means are swapped in
           ("PIP_topadj" in the deck — the far end of the PIP-side chain —
           so the bridge meets in the middle; "PIP" for the raw variant).

    Returns a DataFrame shaped like the harmonized file with
    source = 'WID_posttax_rescaled'.
    """
    if countries is None:
        tgt_c = set(h.loc[h.source == mean_source, "country"])
        wid_c = set(h.loc[h.source == WID_BASE_SOURCE, "country"])
        countries = sorted(tgt_c & wid_c)

    out = []
    for c in countries:
        tgt = h[(h.source == mean_source) & (h.country == c)]
        wid = h[(h.source == WID_BASE_SOURCE) & (h.country == c)].sort_values("p_low").copy()
        assert len(tgt) == 109 and len(wid) == 109, f"missing bins for {c}"

        tgt_mean = (tgt["average"] * tgt["pop"]).sum() / tgt["pop"].sum()
        wid_mean = (wid["average"] * wid["pop"]).sum() / wid["pop"].sum()
        assert wid_mean > 0, f"non-positive WID mean for {c}"
        factor = tgt_mean / wid_mean

        wid["average"] = wid["average"] * factor
        # Shares are scale-invariant, so they are unchanged — but recompute
        # for exactness (guards against future column changes).
        wid["share"] = (wid["average"] * wid["pop"]) / (wid["average"] * wid["pop"]).sum()
        wid["source"] = "WID_posttax_rescaled"
        out.append(wid)
    return pd.concat(out, ignore_index=True)
