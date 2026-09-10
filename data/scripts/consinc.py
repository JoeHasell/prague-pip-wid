"""
consinc.py — THE definition of the income-basis-adjusted PIP series
("PIP_consinc").

THE METHOD
----------
PIP's headline series measures INCOME for some countries and CONSUMPTION for
others. This series puts everyone on an income basis:

  - income countries:      identical to PIP (pass-through);
  - consumption countries: each percentile bin's average is mapped through
    the regression fitted on PIP's dual country-years (04_fit_consinc.py):

        y_hat_p = exp(alpha_p) * c_p ** beta_p

    with (alpha_p, beta_p) estimated per 1%-percentile bin. Our 109-bin
    structure maps 1:1 onto the fit's bins for p1..p99; the ten 0.1% bins
    inside the top 1% all use the p = 100 coefficients — the structure
    within the top 1% is carried by each sub-bin's own consumption value.

Which countries count as consumption-based comes from
data/raw/pip/pip_welfare_types.csv (also written by 04_fit_consinc.py):
the welfare type of each country's most recent national observation in the
PIP percentiles table. Countries absent from that lookup are passed through
unadjusted (and counted in the returned report).

CAVEATS (documented, accepted)
------------------------------
- The regression sample (19 countries, 88 country-years) contains no
  Sub-Saharan Africa or South Asia; applying it there is an out-of-sample
  transfer.
- Monotonicity of the adjusted series is checked but NOT enforced; with
  beta_p varying smoothly it holds in practice.
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# THE METHOD, since 2026-09-09: WID's scaled-logit correction profile
# ---------------------------------------------------------------------------
# Chancel, Cogneau, Gethin & Myczkowski (2019), "How Large Are African
# Inequalities?", WID.world Working Paper 2019/13, section 3.2.
#
# Let Q_I(p) and Q_C(p) be the income and consumption levels at the SAME rank p.
# Their ratio — the "correction profile" — is modelled as a scaled logit:
#
#       c1(p) = Q_I(p) / Q_C(p) = a + b * log(p / (1 - p))
#
# and a consumption distribution is converted by multiplying through:
#
#       Q_I(p) = c1(p) * Q_C(p)
#
# WHY THIS SHAPE. Poor households dissave and receive transfers, so consumption
# exceeds income at the bottom; rich households save, so income exceeds
# consumption at the top. The ratio therefore rises with rank, roughly linearly
# through the middle and steeply in both tails — which is exactly a straight
# line in logit space. b measures how much more unequal income is than
# consumption; a sets the level (it factors out as a*(1 + (b/a)*logit p), so the
# SHAPE is governed by b/a).
#
# WHY WID'S PARAMETERS AND NOT OURS. Fitting this form to PIP's own 88 dual
# country-years gives a = 1.13, b = 0.05 — a profile in which income exceeds
# consumption at EVERY rank, crossing over at about P12 rather than P79. That
# contradicts the mechanism the form encodes. The reason is the sample: 73 of
# the 88 pairs compare TWO DIFFERENT SURVEYS (a household budget survey for
# consumption against EU-SILC for income), and EU-SILC simply reports more at
# every rank, so the gap loads onto a. Restricting to the 15 same-instrument
# pairs fixes the FIT (R^2 0.42 -> 0.90) but not the level, because 9 of those
# 15 are the Philippines, which behaves the same way. And none of the 88 are
# from Sub-Saharan Africa or South Asia, where the mapping is actually applied.
# WID's 21 surveys are Cote d'Ivoire, Ghana, Guinea, Madagascar, Uganda, India
# and Thailand — the right kind of comparison, and the right regions.
#
# Choosing WID's parameters over ours moves the top-adjusted between-country
# share from 56.8% to 54.2% (2023); the functional form itself is nearly a wash
# against the superseded per-percentile regression (55.2%).
#
# WHAT THIS REPLACED. Until 2026-09-09 the deck used a per-percentile log-log
# regression, ln y_p = alpha_p + beta_p ln c_p, fitted on those same 88 pairs
# (see bin_to_fit_percentile below, still used by the local reference scripts
# 04 and 13). Two problems: it made the correction depend on the income LEVEL
# rather than the rank, and its coefficients existed only at percentile
# resolution, so the ten 0.1% bins inside the top 1% had to borrow the p = 100
# pair — an extrapolation that flattened inequality inside the top percentile.
# The logit profile is a continuous function of rank, so it evaluates at any
# resolution and that problem disappears.
WID_PROFILE_A = 0.85          # level; WID Table A.1 estimates span 0.77-0.92
WID_PROFILE_B = 0.12          # slope; WID's benchmark, and THE deck's baseline

# WID report the slope as a RANGE, not a point: three values spanning how much
# more unequal income is than consumption. b is the whole shape of the
# correction (a factors out — see above), so this range is the honest
# uncertainty in the consumption -> income step, and 32_fig_consinc_topadj_cross.py
# crosses it with the six top-adjustment variants. The middle value is the
# baseline shown in the bridging slides.
WID_PROFILE_B_SCENARIOS = (0.10, 0.12, 0.14)
assert WID_PROFILE_B in WID_PROFILE_B_SCENARIOS, \
    "the baseline slope must be one of WID's three, or the cross has no baseline column"


def correction_profile(p, a=WID_PROFILE_A, b=WID_PROFILE_B):
    """Income-to-consumption ratio at rank p (0 < p < 1). See above."""
    p = np.asarray(p, dtype=float)
    assert (p > 0).all() and (p < 1).all(), "rank must be strictly inside (0, 1)"
    return a + b * np.log(p / (1.0 - p))


def build_pip_consinc_profile(bins, welfare_types, a=WID_PROFILE_A, b=WID_PROFILE_B,
                              base_series="PIP", out_series="PIP_consinc"):
    """PIP put on an income basis via the scaled-logit profile.

    Consumption-based countries are multiplied through by correction_profile()
    evaluated at each bin's MIDPOINT rank; income-based countries pass through
    untouched. Keeps the full 109-bin structure — no aggregation of the top 1%
    is needed, because the profile is continuous in rank.
    """
    out = []
    for c, g in bins[bins["series"] == base_series].groupby("country", observed=True):
        g = g.sort_values("p_low").copy()
        if welfare_types.get(c) == "consumption":
            mid = ((g["p_low"] + g["p_high"]) / 2.0).to_numpy(dtype=float)
            g["avg"] = g["avg"].to_numpy(dtype=float) * correction_profile(mid, a, b)
        g["series"] = out_series
        out.append(g)
    return pd.concat(out, ignore_index=True)


def bin_to_fit_percentile(p_high):
    """Map a harmonized bin (by its upper bound, fraction) to the fit's
    1%-percentile index: p10p11 -> 11, p0p1 -> 1, all top-1% bins -> 100.

    The epsilon absorbs floating-point noise in p_high before the ceil. It has to
    be generous: the ETL stores p_high as float32, so p97p98 arrives as
    0.98000001907 and p98p99 as 0.99000000954 — with a 1e-9 epsilon those ceil to
    99 and 100 instead of 98 and 99, silently shifting the coefficients by one
    percentile for every bin whose float32 value rounds upward. 1e-4 in percentile
    units is far below the narrowest bin boundary spacing (0.1) and comfortably
    above float32 error (~1e-5 at this magnitude).
    """
    return min(100, int(np.ceil(p_high * 100 - 1e-4)))


def build_pip_consinc(h, model, welfare, countries=None):
    """Build the income-basis-adjusted PIP series.

    Args:
        h: harmonized DataFrame.
        model: DataFrame with columns percentile, alpha, beta
               (data/processed/consinc_model.csv).
        welfare: DataFrame with columns country, welfare_type
               (data/raw/pip/pip_welfare_types.csv).
        countries: list of names, or None for all PIP countries.

    Returns (DataFrame with source='PIP_consinc', report dict).
    """
    alpha = model.set_index("percentile")["alpha"]
    beta = model.set_index("percentile")["beta"]
    wtype = dict(zip(welfare["country"], welfare["welfare_type"]))

    pip = h[h.source == "PIP"]
    if countries is None:
        countries = sorted(pip["country"].unique())

    out = []
    report = {"income_passthrough": 0, "consumption_adjusted": 0, "not_in_lookup": []}
    for c in countries:
        g = pip[pip.country == c].sort_values("p_low").copy()
        assert len(g) == 109, f"missing bins for {c}"
        kind = wtype.get(c)
        if kind is None:
            report["not_in_lookup"].append(c)
        if kind == "consumption":
            k = g["p_high"].map(bin_to_fit_percentile)
            cvals = g["average"].to_numpy(dtype=float)
            assert (cvals > 0).all(), f"non-positive consumption for {c}"
            g["average"] = np.exp(k.map(alpha).to_numpy()) * cvals ** k.map(beta).to_numpy()
            adj = g["average"].to_numpy()
            if not (np.diff(adj) >= -1e-9).all():
                report.setdefault("non_monotone", []).append(c)
            g["share"] = (g["average"] * g["pop"]) / (g["average"] * g["pop"]).sum()
            report["consumption_adjusted"] += 1
        else:
            report["income_passthrough"] += 1
        g["source"] = "PIP_consinc"
        out.append(g)
    return pd.concat(out, ignore_index=True), report
