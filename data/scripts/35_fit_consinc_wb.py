"""
35_fit_consinc_wb.py — re-fit Wollburg, Hallegatte & Mahler (2023)'s consumption model on
PIP's dual country-years, at 2017 PPP (the replication check) and at 2021 PPP (the deck's
constants).

    data/processed/consinc_wb_fit.json

WHY
---
The deck's parallel consumption->income chain (consinc.py, "A SECOND METHOD") inverts

    ln(con_p) = ln( inc_p**a + g0 + g1 * ln(inc_median) )

which Wollburg, Hallegatte & Mahler (World Bank PRWP 10318, appendix A) fitted on PIP's dual
surveys in 2017 PPP $/day and reported as a = 0.93, g0 = 0.68, g1 = 0.26. The formula is
not scale-free — an additive floor and an exponent — so constants estimated at 2017 prices do
not belong on the deck's 2021-PPP bins. This script runs the paper's exercise on today's PIP
catalog at both price bases: the 2017 fit tells us how close we get to the paper, the 2021
fit is what the deck uses.

WHAT IT FOUND (2026-09-22)
--------------------------
Weighting decides whether the paper comes back. With every country-year weighted equally the
88 pairs-sets at 2017 PPP give a = 0.905, g0 = 0.363, g1 = 0.334 (adj. R2 0.928; the paper:
0.93 / 0.68 / 0.26, 0.965) — Poland alone is 17 of the 88 country-years and Romania 13, so this
is largely a fit to Eastern Europe's EU-SILC years. Weighting each COUNTRY equally instead
(1 / its number of surveys) gives a = 0.929, g0 = 0.612, g1 = 0.381 with weighted fit
statistics of 0.9655 and 0.66 below the poverty line — the paper's exponent and the paper's
R2, near enough to suggest that is how (or on what balance of countries) they estimated it.
g0 and g1 trade off against each other (correlation -0.9), so the floor they imply agrees
better than the two numbers separately. Neither thresholds instead of bin averages nor the
paper's 16 countries alone change this picture. THE DECK USES THE COUNTRY-BALANCED FIT AT
2021 PPP (a = 0.932, g0 = 0.632, g1 = 0.411): it is the one that reproduces the paper's
exponent, each country counts once, and inverted it predicts PIP's income percentiles from
consumption best in-sample (consinc.main()). Every record in the results file also carries
its parameters' UNWEIGHTED fit on all pairs, so the two objectives are comparable.

HOW
---
- Sample: every national PIP country-year with BOTH welfare types (88 country-years, 19
  countries: the paper's 16 plus Kosovo, Saint Lucia and Turkey); the paper's 16 alone as a
  sensitivity, and a country-balanced fit (Poland alone is 17 of the 88 country-years).
- Pairs: the income and consumption bin AVERAGES at the same percentile — what the deck
  applies the formula to. inc_median is the country-year's median income exactly as the
  deck computes it at apply time (consinc.wb_median: mean of percentile bins 50 and 51).
- Estimator: nonlinear least squares in logs, Levenberg-Marquardt in plain numpy (the
  pipeline's only dependencies are pandas and pyarrow), from three starts that must agree.
- The two-parameter model ln(inc**a + gamma) is fitted alongside, as in the paper.

Run:  python data/scripts/35_fit_consinc_wb.py
      (network: the OWID catalog. A ONE-OFF — not run by refresh_from_etl.py; the results
      file is committed and consinc.main() checks the hardcoded constants against it.)
"""

import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd

import consinc
import etl_source as es

OUT_FILE = Path(__file__).resolve().parents[1] / "processed" / "consinc_wb_fit.json"

PPP_VERSIONS = (2017, 2021)
# The international poverty line of each PPP round, $/day: "below the line" means the pair's
# INCOME bin average is below it.
IPL = {2017: 2.15, 2021: 3.00}
PAPER_COUNTRIES = frozenset({
    "Albania", "Bulgaria", "Croatia", "Estonia", "Haiti", "Hungary", "Latvia", "Lithuania",
    "Montenegro", "Nicaragua", "Philippines", "Poland", "Romania", "Russia", "Serbia", "Slovakia",
})
PAPER_2017 = {
    "a": 0.93, "g0": 0.68, "g1": 0.26, "adj_r2": 0.965,
    "two_param": {"a": 0.94, "gamma": 1.04, "r2_below_ipl": 0.887},
    "n_surveys": 150, "n_countries": 16, "ppp": 2017,
    "source": "Wollburg, Hallegatte & Mahler (2023), World Bank PRWP 10318, appendix A",
}
STARTS = ((0.93, 0.68, 0.26), (1.0, 0.0, 0.0), (0.8, 2.0, -0.5))
# The fit the deck's constants come from: 2021 PPP, every country weighted equally.
DECK_PPP, DECK_SAMPLE = 2021, "all_country_balanced"
SAMPLES = (("all", None), ("paper16", PAPER_COUNTRIES), ("all_country_balanced", "balanced"))
MU_FLOOR = 1e-12
COLUMNS = ["country", "year", "ppp_version", "welfare_type", "reporting_level", "percentile", "avg"]


def main():
    print("Reading PIP's percentiles from the OWID catalog…")
    df = load_percentiles()
    pairs = {ppp: dual_pairs(df, ppp) for ppp in PPP_VERSIONS}
    keys = {ppp: set(map(tuple, p[["country", "year"]].drop_duplicates().to_numpy())) for ppp, p in pairs.items()}
    assert keys[2017] == keys[2021], "the two PPP rounds cover different dual country-years"
    country_years = sorted(keys[2021])
    print(f"  {len(country_years)} dual national country-years, "
          f"{len({c for c, _ in country_years})} countries, identical at both PPP rounds")

    fits = []
    for ppp in PPP_VERSIONS:
        for sample, spec in SAMPLES:
            fits.append(run_fit(pairs[ppp], ppp, sample, spec))

    def record(ppp, sample):
        return next(f for f in fits if f["ppp"] == ppp and f["sample"] == sample)

    # Structural replication checks on both 2017 estimators; the gap to the paper for each.
    gaps = {s: replication_checks(record(2017, s)) for s in ("all", "all_country_balanced")}
    gap = gaps["all_country_balanced"]
    rec_2021 = record(DECK_PPP, DECK_SAMPLE)

    deck = {k: consinc.wb_round(rec_2021[k]) for k in ("a", "g0", "g1")}
    out = {
        "generated_by": "35_fit_consinc_wb.py",
        "generated_on": datetime.date.today().isoformat(),
        "source": es.PIP_PERCENTILES_URL,
        "pip_version": es.PIP_VERSION,
        "model": "ln(con_p) = ln(inc_p**a + g0 + g1 * ln(inc_median))",
        "estimator": "nonlinear least squares in logs; Levenberg-Marquardt (numpy); starts " + repr(STARTS),
        "quantile_measure": "avg: the percentile bin average, $/day per capita, national surveys",
        "median_definition": "mean of income percentile bins 50 and 51 (consinc.wb_median)",
        "below_ipl": "pairs whose INCOME bin average is below the round's international poverty line",
        "ipl": {str(k): v for k, v in IPL.items()},
        "rounding": f"{consinc.WB_ROUND_SIG} significant digits (consinc.wb_round)",
        "paper_2017": dict(PAPER_2017, gap_vs_2017_all=gaps["all"], gap_vs_2017_country_balanced=gap),
        "deck": dict(deck, ppp=DECK_PPP, sample=DECK_SAMPLE),
        "country_years": [[c, int(y)] for c, y in country_years],
        "fits": fits,
    }
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print("\n%-6s %-22s %5s %8s %8s %8s %8s %11s %8s   %-24s" % (
        "PPP", "sample", "c-y", "a", "g0", "g1", "adj R2", "R2<IPL", "R2 unw.", "2-param a / gamma / adj R2"))
    print("%-6s %-22s %5s %8.2f %8.2f %8.2f %8.3f %11s %8s   %.2f / %.2f / -" % (
        "2017", "paper (reference)", "~75", PAPER_2017["a"], PAPER_2017["g0"], PAPER_2017["g1"],
        PAPER_2017["adj_r2"], "0.887 (2p)", "-", PAPER_2017["two_param"]["a"], PAPER_2017["two_param"]["gamma"]))
    for f in fits:
        t = f["two_param"]
        print("%-6s %-22s %5d %8.4f %8.4f %8.4f %8.4f %6.3f (n=%3d) %8.4f   %.4f / %.4f / %.4f" % (
            f["ppp"], f["sample"], f["n_country_years"], f["a"], f["g0"], f["g1"], f["adj_r2"],
            f["r2_below_ipl"], f["n_below_ipl"], f["unweighted"]["r2"], t["a"], t["gamma"], t["adj_r2"]))
    print("  (weighted fits report weighted R2; 'R2 unw.' evaluates each parameter set unweighted on all pairs)")
    for s, g in gaps.items():
        print(f"\nreplication check on 2017/{s} passed; gap to the paper: a {g['a']:+.3f}, g0 {g['g0']:+.3f}, "
              f"g1 {g['g1']:+.3f}, adj R2 {g['adj_r2']:+.3f}")
    print(f"\nhardcode in consinc.py:  WB_EXPONENT = {deck['a']}  WB_FLOOR_INTERCEPT = {deck['g0']}  "
          f"WB_FLOOR_SLOPE = {deck['g1']}")
    current = (consinc.WB_EXPONENT, consinc.WB_FLOOR_INTERCEPT, consinc.WB_FLOOR_SLOPE)
    if current != (deck["a"], deck["g0"], deck["g1"]):
        print(f"  ** consinc.py currently has {current} — update it, or consinc.main() will fail its check")
    else:
        print("  consinc.py already carries these constants")
    print(f"\nSaved: {OUT_FILE.relative_to(OUT_FILE.parents[2])}")


def load_percentiles():
    """PIP's percentiles table, national, income or consumption, both PPP rounds."""
    df = pd.read_parquet(es.PIP_PERCENTILES_URL, columns=COLUMNS)
    for c in ("country", "welfare_type", "reporting_level"):
        df[c] = df[c].astype(str)
    d = df[(df["reporting_level"] == "national") & df["welfare_type"].isin(["income", "consumption"])].copy()
    d["year"] = d["year"].astype(int)
    d["ppp_version"] = d["ppp_version"].astype(int)
    d["percentile"] = d["percentile"].astype(int)
    d["avg"] = d["avg"].astype("float64")
    return d


def dual_pairs(df, ppp):
    """Income-consumption pairs at the same percentile for every country-year with both welfare
    types: country, year, percentile, income, consumption, inc_median."""
    d = df[df["ppp_version"] == ppp]
    k = d.groupby(["country", "year"])["welfare_type"].nunique()
    dual = k[k == 2].index
    s = d.set_index(["country", "year"]).loc[dual].reset_index()
    counts = s.groupby(["country", "year", "welfare_type"]).size()
    assert (counts == 100).all(), f"not 100 percentile bins everywhere: {counts[counts != 100].head().to_dict()}"
    piv = (s.pivot_table(index=["country", "year", "percentile"], columns="welfare_type", values="avg")
            .reset_index().sort_values(["country", "year", "percentile"]))
    assert piv["income"].notna().all() and piv["consumption"].notna().all()
    assert (piv["income"] > 0).all() and (piv["consumption"] > 0).all(), "non-positive bin averages"
    med = (piv.groupby(["country", "year"])["income"]
              .apply(lambda g: consinc.wb_median(g.to_numpy(dtype=float)))
              .rename("inc_median").reset_index())
    return piv.merge(med, on=["country", "year"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# The models, their Jacobians (of ln mu with respect to the parameters), and the fitter
# ---------------------------------------------------------------------------
def model3(theta, inc, lnm):
    a, g0, g1 = theta
    return np.maximum(inc ** a + g0 + g1 * lnm, MU_FLOOR)


def jac3(theta, inc, lnm, mu):
    a = theta[0]
    return np.column_stack([inc ** a * np.log(inc) / mu, 1.0 / mu, lnm / mu])


def model2(theta, inc, lnm):
    a, gamma = theta
    return np.maximum(inc ** a + gamma, MU_FLOOR)


def jac2(theta, inc, lnm, mu):
    a = theta[0]
    return np.column_stack([inc ** a * np.log(inc) / mu, 1.0 / mu])


def lm_fit(y, inc, lnm, start, model, jac, weights=None, max_iter=200, tol=1e-12):
    """Levenberg-Marquardt for r(theta) = ln(model) - y, optionally weighted (rows scaled by
    sqrt(w)). Returns theta, residuals, iterations, and whether it converged."""
    theta = np.asarray(start, dtype=float)
    sw = np.ones_like(y) if weights is None else np.sqrt(np.asarray(weights, dtype=float))

    def residuals(t):
        return (np.log(model(t, inc, lnm)) - y) * sw

    r = residuals(theta)
    sse = float(r @ r)
    lam = 1e-3
    for it in range(1, max_iter + 1):
        mu = model(theta, inc, lnm)
        J = jac(theta, inc, lnm, mu) * sw[:, None]
        JtJ = J.T @ J
        g = J.T @ r
        while True:
            delta = np.linalg.solve(JtJ + lam * np.diag(np.diag(JtJ)), -g)
            r_new = residuals(theta + delta)
            sse_new = float(r_new @ r_new)
            if sse_new < sse:
                theta, r, sse = theta + delta, r_new, sse_new
                lam = max(lam / 10.0, 1e-15)
                break
            lam *= 10.0
            if lam > 1e12:
                # No step can lower the SSE any further: converged if the last proposed step
                # was already negligible, a genuine failure otherwise.
                return theta, r, it, bool(np.max(np.abs(delta)) < 1e-6 * (1.0 + np.max(np.abs(theta))))
        if np.max(np.abs(delta)) < tol * (1.0 + np.max(np.abs(theta))):
            return theta, r, it, True
    return theta, r, max_iter, False


def fit(y, inc, lnm, model, jac, starts, weights=None):
    """Fit from every start; the optima must agree. Returns the parameters, residuals, standard
    errors and the parameter correlation matrix."""
    results = [lm_fit(y, inc, lnm, s, model, jac, weights) for s in starts]
    assert all(ok for *_, ok in results), "Levenberg-Marquardt did not converge from every start"
    thetas = np.array([t for t, *_ in results])
    ref = thetas[0]
    assert np.allclose(thetas, ref, rtol=1e-6, atol=1e-8), f"the starts disagree: {thetas}"
    theta, r, n_iter, _ = results[0]
    mu = model(theta, inc, lnm)
    assert mu.min() > MU_FLOOR * 1e6, "the clip on inc**a + gamma was active at the optimum"
    sw = np.ones_like(y) if weights is None else np.sqrt(np.asarray(weights, dtype=float))
    J = jac(theta, inc, lnm, mu) * sw[:, None]
    n, k = len(y), len(theta)
    cov = np.linalg.inv(J.T @ J) * (float(r @ r) / (n - k))
    se = np.sqrt(np.diag(cov))
    corr = cov / np.outer(se, se)
    return theta, r, se, corr, n_iter


def r2_stats(r, y, k, below, weights=None):
    """R2, adjusted R2 and the R2 on the below-the-line pairs. `r` are the (possibly weighted)
    residuals; for the unweighted fit they are ln(mu) - y."""
    sw = np.ones_like(y) if weights is None else np.sqrt(np.asarray(weights, dtype=float))
    yw = y * sw
    sse = float(r @ r)
    sst = float(((yw - yw.mean()) ** 2).sum())
    n = len(y)
    rb, yb = r[below], yw[below]
    r2_below = 1.0 - float(rb @ rb) / float(((yb - yb.mean()) ** 2).sum()) if below.sum() > 2 else float("nan")
    return {"r2": 1.0 - sse / sst, "adj_r2": 1.0 - (sse / (n - k)) / (sst / (n - 1)),
            "r2_below_ipl": r2_below, "n_below_ipl": int(below.sum())}


def run_fit(pairs, ppp, sample, spec):
    p = pairs if spec is None or spec == "balanced" else pairs[pairs["country"].isin(spec)]
    inc = p["income"].to_numpy(dtype=float)
    con = p["consumption"].to_numpy(dtype=float)
    lnm = np.log(p["inc_median"].to_numpy(dtype=float))
    y = np.log(con)
    weights = None
    if spec == "balanced":
        n_years = p.groupby("country")["year"].transform("nunique").to_numpy(dtype=float)
        weights = 1.0 / n_years
    below = inc < IPL[ppp]

    theta, r, se, corr, n_iter = fit(y, inc, lnm, model3, jac3, STARTS, weights)
    theta2, r2_, se2, _, n_iter2 = fit(y, inc, lnm, model2, jac2, ((0.94, 1.04), (1.0, 0.0)), weights)
    s3 = r2_stats(r, y, 3, below, weights)
    s2 = r2_stats(r2_, y, 2, below, weights)
    a, g0, g1 = (float(v) for v in theta)
    # The same parameters evaluated UNWEIGHTED on every pair, so weighted and unweighted fits
    # can be compared on one footing.
    r_unw = np.log(model3(theta, inc, lnm)) - y
    unweighted = r2_stats(r_unw, y, 3, below)
    return {
        "ppp": ppp, "sample": sample, "weighted": spec == "balanced",
        "n_pairs": int(len(p)), "n_country_years": int(p.groupby(["country", "year"]).ngroups),
        "n_countries": int(p["country"].nunique()),
        "a": a, "g0": g0, "g1": g1,
        "se": {"a": float(se[0]), "g0": float(se[1]), "g1": float(se[2])},
        "corr_g0_g1": float(corr[1, 2]),
        "gamma_at_sample_median_lnm": float(g0 + g1 * np.median(lnm)),
        "median_income_range": [float(np.exp(lnm.min())), float(np.exp(lnm.max()))],
        "n_iter": int(n_iter), **s3,
        "unweighted": {"r2": unweighted["r2"], "adj_r2": unweighted["adj_r2"], "r2_below_ipl": unweighted["r2_below_ipl"]},
        "two_param": {"a": float(theta2[0]), "gamma": float(theta2[1]),
                      "se": {"a": float(se2[0]), "gamma": float(se2[1])}, "n_iter": int(n_iter2), **s2},
    }


def replication_checks(rec):
    """The structural checks on the 2017 / all fit (a numeric match to the paper is not on
    the table — see the module docstring). Returns the gap to the paper."""
    assert 0.85 <= rec["a"] <= 0.97, f"exponent out of band: {rec['a']}"
    assert rec["g1"] > 0, "the consumption floor should rise with median income"
    assert rec["g0"] > -1.0, "intercept too negative for the deck's bracket proof"
    assert rec["adj_r2"] > 0.90, f"adj R2 {rec['adj_r2']}"
    assert rec["adj_r2"] > rec["two_param"]["adj_r2"], "the median term should improve the fit"
    assert rec["r2_below_ipl"] > rec["two_param"]["r2_below_ipl"], \
        "the median term should improve the fit below the poverty line, as in the paper"
    return {k: rec[k] - PAPER_2017[k] for k in ("a", "g0", "g1", "adj_r2")}


if __name__ == "__main__":
    main()
