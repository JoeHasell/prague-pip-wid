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


def bin_to_fit_percentile(p_high):
    """Map a harmonized bin (by its upper bound, fraction) to the fit's
    1%-percentile index: p10p11 -> 11, p0p1 -> 1, all top-1% bins -> 100."""
    return min(100, int(np.ceil(p_high * 100 - 1e-9)))


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
