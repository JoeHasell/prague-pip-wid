"""
consinc.py — THE definition of the income-basis-adjusted PIP series
("PIP_consinc").

TWO METHODS (2026-09-21)
------------------------
The deck's BASELINE is WID's scaled-logit correction profile — see the block
"THE METHOD, since 2026-09-09" below; everything on the bridging slides uses it.
A SECOND method runs in parallel as a comparison series, PIP_consinc_wb: the
inverse of Wollburg, Hallegatte & Mahler (2023)'s income->consumption fit, whose
income concept is PIP's own disposable income — see "A SECOND METHOD" below. It
appears only on the reference-year dataset (33_) and the year-vs-year scatters
(34_), never in the bridging column. The section "THE METHOD" that follows
describes the per-percentile regression both of these replaced; it is kept for
the local reference scripts (04, 13).

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


# ---------------------------------------------------------------------------
# A SECOND METHOD, IN PARALLEL (2026-09-21): the Wollburg-Hallegatte-Mahler inverse
# ---------------------------------------------------------------------------
# Wollburg, Hallegatte & Mahler (2023), "The Climate Implications of Ending
# Global Poverty", World Bank Policy Research Working Paper 10318, appendix A.
# On the 150 PIP surveys (16 countries: Albania, Bulgaria, Croatia, Estonia,
# Haiti, Hungary, Latvia, Lithuania, Montenegro, Nicaragua, Philippines, Poland,
# Romania, Russia, Serbia, Slovakia) that publish BOTH welfare types in the same
# year, collapsed to 100 quantile pairs (same rank, not the same people), they fit
#
#       ln(con_p) = ln( inc_p**0.93 + 0.68 + 0.26 * ln(inc_median) )     adj. R2 0.965
#
# derived from two three-parameter log-normals: 0.93 is sigma_con / sigma_inc
# (how much more compressed consumption is than income) and gamma = 0.68 +
# 0.26 ln m is a "consumption floor" that rises with the country's median
# INCOME m. On the same pairs WID's ratio form (correction_profile above) fits
# with R2 0.772.
#
# WHY IT IS HERE. Its income is PIP's own — disposable, after taxes and
# transfers — which is the concept PIP's income countries are on, whereas the
# WID profile was estimated on pre-tax income. That is what this parallel
# series exists to study. It is NOT the baseline, for two reasons the docs say
# plainly: it is fitted in the OTHER direction (inverting E[con|inc] is not
# E[inc|con]), and on the European-heavy PIP dual sample that the block above
# rejects for the baseline — EU-SILC income against budget-survey consumption,
# nothing from Sub-Saharan Africa or South Asia, where the conversion is
# applied. In-sample, on the deck's 19 cached dual surveys, the inverse still
# predicts PIP's income percentiles from consumption better than the WID
# profile does; main() prints that table.
#
# THE INVERSE, per country-year on the 100-bin grid:
#
#       gamma = 0.68 + 0.26 ln m,   m solved from   con_median = m**0.93 + gamma(m)
#       inc_p = max( clip(con_p - gamma, 0)**(1/0.93), WB_INCOME_FLOOR )
#
# The root is unique: the right-hand side is strictly increasing in m and goes
# to -inf as m -> 0. Bins whose consumption is at or below gamma have no real
# income under the formula, and bins just above it invert to near zero. They
# are floored at PIP's own bottom code, $0.28/day — the smallest value PIP
# publishes, and already the deck's PIP floor (etl_mld.py) — not at the MLD's
# $0.01 zero replacement, which a single bin can dominate. In 2023 this touches
# 44 of the 103 consumption countries (Zambia and South Sudan 16 bins each,
# Mozambique 13, DR Congo 12): their bottoms become a flat run at $0.28.
#
# UNITS. The paper's constants are in 2017 PPP $/day per capita; the deck's
# bins are 2021 PPP $/day. The formula is not scale-free (an additive floor and
# an exponent), so strictly the constants belong to 2017 prices. By decision
# (2026-09-21) they are applied to the 2021-price values as they are — no
# re-basing. The pure US price factor 2017 -> 2021 is 1.1055, should that ever
# be revisited.
WB_EXPONENT = 0.93            # sigma_con / sigma_inc
WB_FLOOR_INTERCEPT = 0.68     # gamma = WB_FLOOR_INTERCEPT + WB_FLOOR_SLOPE * ln(median income)
WB_FLOOR_SLOPE = 0.26
WB_INCOME_FLOOR = 0.28        # $/day: PIP's own bottom code (see above)
WB_MEDIAN_BINS = (49, 50)     # p49p50 and p50p51: the two bins straddling rank 0.5


def wb_median(avg):
    """The median of a 100-equal-bin distribution: the mean of the two bins that
    straddle rank 0.5, by position after sorting by rank."""
    avg = np.asarray(avg, dtype=float)
    assert len(avg) == 100, f"the Wollburg inverse needs the 100-bin grid, got {len(avg)} bins"
    return float(0.5 * (avg[WB_MEDIAN_BINS[0]] + avg[WB_MEDIAN_BINS[1]]))


def wb_consumption_floor(median_income):
    """gamma(m) = 0.68 + 0.26 ln m."""
    return WB_FLOOR_INTERCEPT + WB_FLOOR_SLOPE * np.log(median_income)


def wb_consumption_from_income(inc, median_income):
    """The paper's forward model: consumption at each rank from income at that rank."""
    return np.asarray(inc, dtype=float) ** WB_EXPONENT + wb_consumption_floor(median_income)


def wb_median_income(median_consumption, tol=1e-12, max_iter=200):
    """Solve con_median = m**0.93 + 0.68 + 0.26 ln m for the median income m, by bisection.

    g(m) = m**0.93 + gamma(m) - con_median is strictly increasing, g -> -inf as m -> 0+,
    and g((c + 1)**(1/0.93) + 1) > 0, so the bracket below always holds and the root is
    unique. Bisection rather than scipy: the pipeline's only dependencies are pandas and
    pyarrow.
    """
    c = float(median_consumption)
    assert c > 0, "median consumption must be positive"

    def g(m):
        return m ** WB_EXPONENT + wb_consumption_floor(m) - c

    lo, hi = 1e-9, (c + 1.0) ** (1.0 / WB_EXPONENT) + 1.0
    assert g(lo) < 0 < g(hi), f"bracket failed for median consumption {c}"
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        if g(mid) < 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol * max(1.0, hi):
            break
    return 0.5 * (lo + hi)


def wb_country_parameters(con):
    """What the inverse solved for one country — its medians, the floor, and how many
    bins the floor rule caught. `con` are the 100 bin averages in rank order."""
    con = np.asarray(con, dtype=float)
    med_con = wb_median(con)
    m = wb_median_income(med_con)
    gamma = float(wb_consumption_floor(m))
    raw = np.clip(con - gamma, 0.0, None) ** (1.0 / WB_EXPONENT)
    return {"median_consumption": med_con, "median_income": m, "gamma": gamma,
            "n_below_gamma": int((con <= gamma).sum()), "n_floored": int((raw < WB_INCOME_FLOOR).sum())}


def wb_income_from_consumption(con, floor=WB_INCOME_FLOOR):
    """The inverse: 100 consumption bin averages in rank order -> income bin averages."""
    con = np.asarray(con, dtype=float)
    assert (con > 0).all(), "non-positive consumption bins"
    gamma = wb_consumption_floor(wb_median_income(wb_median(con)))
    inc = np.clip(con - gamma, 0.0, None) ** (1.0 / WB_EXPONENT)
    return np.maximum(inc, floor)


def wb_verify_inverse(con, inc, floor=WB_INCOME_FLOOR, rtol=1e-9):
    """Assert that `inc` is wb_income_from_consumption(con): the forward model reproduces
    every bin the floor did not touch, every floored bin really sat at or below the
    floor's consumption, and the result is non-decreasing in rank."""
    con = np.asarray(con, dtype=float)
    inc = np.asarray(inc, dtype=float)
    back = wb_consumption_from_income(inc, wb_median_income(wb_median(con)))
    floored = np.isclose(inc, floor)
    assert np.allclose(back[~floored], con[~floored], rtol=rtol), "the Wollburg inverse does not round-trip"
    assert (con[floored] <= back[floored] + 1e-9).all(), "a floored bin sits above the floor's consumption"
    assert (np.diff(inc) >= -1e-9).all(), "the Wollburg income basis is not monotone in rank"


def build_pip_consinc_wb(bins, welfare_types, base_series="PIP", out_series="PIP_consinc_wb",
                         floor=WB_INCOME_FLOOR):
    """PIP put on an income basis via the Wollburg et al. inverse — the same frame
    contract as build_pip_consinc_profile: consumption countries are converted bin by
    bin, income countries pass through untouched. Needs the deck's 100-bin grid (the
    median is read by position), so call it after etl_source.aggregate_to_percentiles."""
    out = []
    for c, g in bins[bins["series"] == base_series].groupby("country", observed=True):
        g = g.sort_values("p_low").copy()
        if welfare_types.get(c) == "consumption":
            p_low = g["p_low"].to_numpy(dtype=float)
            assert len(g) == 100 and abs(p_low[WB_MEDIAN_BINS[0]] - 0.49) < 1e-4, \
                f"{c}: the Wollburg inverse needs the 100-bin grid (call after aggregate_to_percentiles)"
            g["avg"] = wb_income_from_consumption(g["avg"].to_numpy(dtype=float), floor)
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


def main():
    """Offline self-check of the Wollburg inverse:  python data/scripts/consinc.py

    1. the root-finder recovers a known median income;
    2. on PIP's own dual surveys (both welfare types the same year, the cached
       pip_dual_percentiles) both methods predict the INCOME percentiles from the
       CONSUMPTION ones, against the income PIP actually published.
    """
    import etl_source as es

    for m in (0.5, 2.0, 10.0, 100.0):
        c = m ** WB_EXPONENT + wb_consumption_floor(m)
        assert abs(wb_median_income(c) / m - 1) < 1e-9, m
    print("root recovery: ok for a median income of 0.5, 2, 10 and 100 $/day")

    dual = es.load("pip_dual_percentiles")
    p = (np.arange(100) + 0.5) / 100
    rows = []
    for c, g in dual.groupby("country"):
        if g["welfare_type"].nunique() < 2:
            continue
        cons = g[g["welfare_type"] == "consumption"].sort_values("percentile")["avg"].to_numpy(dtype=float)
        inc = g[g["welfare_type"] == "income"].sort_values("percentile")["avg"].to_numpy(dtype=float)
        if len(cons) != 100 or len(inc) != 100:
            continue
        wb = wb_income_from_consumption(cons)
        wb_verify_inverse(cons, wb)
        prm = wb_country_parameters(cons)
        wid = cons * correction_profile(p)
        e_wb, e_wid = np.log(wb / inc), np.log(wid / inc)
        rows.append({
            "country": c, "year": int(g["year"].iloc[0]), "inc_p50": 0.5 * (inc[49] + inc[50]),
            "m_solved": prm["median_income"], "gamma": prm["gamma"], "floored": prm["n_floored"],
            "rmse_wb": np.sqrt(np.mean(e_wb ** 2)), "rmse_wid": np.sqrt(np.mean(e_wid ** 2)),
            "ratio_wb": np.exp(np.median(e_wb)), "ratio_wid": np.exp(np.median(e_wid)),
            "bot5_wb": e_wb[:5].mean(), "bot5_wid": e_wid[:5].mean(),
            "top5_wb": e_wb[-5:].mean(), "top5_wid": e_wid[-5:].mean(),
        })
    t = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(f"\nIN-SAMPLE, {len(t)} dual surveys — predicting the income percentiles from the consumption ones")
    print("  rmse = root-mean-square log error over the 100 percentiles; ratio = median predicted/actual;")
    print("  bot5/top5 = mean log error over the bottom/top five percentiles; floored = bins at the $0.28 floor")
    print(t.round(3).to_string(index=False))
    print("\n  medians across countries:   Wollburg inverse   WID profile")
    for k, lab in (("rmse", "log RMSE"), ("ratio", "predicted/actual"), ("bot5", "bottom-5 log error"), ("top5", "top-5 log error")):
        print(f"    {lab:<22} {t[k + '_wb'].median():>14.3f}   {t[k + '_wid'].median():>11.3f}")
    print(f"    {'solved median / actual':<22} {(t['m_solved'] / t['inc_p50']).median():>14.3f}")


if __name__ == "__main__":
    main()
