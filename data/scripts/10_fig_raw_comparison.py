"""
10_fig_raw_comparison.py — data for the deck figure "fig-raw-comparison".

THE FIGURE (rendered by components/fig-raw-comparison.js)
----------------------------------------------------------
The raw, before-any-bridging comparison of WID and PIP for three countries
(United States, Indonesia, Nigeria):

  Row 1  Lollipops of P10 (bin p10p11), P90 (bin p90p91) and the country MEAN,
         income $/day on a shared log axis. WID pre-tax per adult on the left,
         PIP on the right.
  Row 2  Stacked bars of the MLD (mean log deviation) LEVEL decomposed into
         between-country and within-country components, computed on the FULL
         distributions of just these three countries — one bar per source.

ALL FIVE series in the harmonized dataset are computed and written to the
JSON; the component chooses which to show (and in what order) via its
`sources` prop. This is what lets the deck "build up" the comparison across
slides: the raw two-column slide and the bridging-steps slide share this one
script and one JSON:
  - WID_pretax_per_adult  : pre-tax national income, per adult (the raw headline)
  - WID_pretax_per_capita : bridging step — same income, per-capita basis
  - WID_posttax_per_adult : post-tax national income, per adult (not currently shown)
  - WID_posttax_per_capita: bridging step — post-tax, per capita
  - PIP                   : disposable income/consumption, per capita (the target)

METHOD NOTES
------------
MLD and its decomposition (population-weighted, over bins i in country c):
    MLD_total   = sum_i w_i * ln(mu / x_i)          w_i = pop_i / total_pop
    within_c    = sum_i in c  (pop_i/pop_c) * ln(mu_c / x_i)
    MLD_within  = sum_c (pop_c/total_pop) * within_c
    MLD_between = sum_c (pop_c/total_pop) * ln(mu / mu_c)
    (identity MLD_total = MLD_within + MLD_between is asserted below)

ZERO INCOMES: WID has zero-income bins at the bottom of the distribution
(here: 5 bins each for Indonesia and Nigeria; PIP has none). ln(0) is
undefined, so — following the convention established in the original research
project, whose sensitivity analysis found the choice moves the between-share
by ~3pp at global scale — zeros are replaced with $0.01/day FOR THE MLD ONLY.
The lollipop values (P10/P90/mean) are unaffected (no zero bins at those
points; means computed on raw values).

The 'pop' weights are each series' own basis: adults for the per-adult WID
series, total population for PIP — this is part of what makes the raw
comparison "unfair", which is the point of the figure.

INPUT   data/processed/pip_wid_harmonized_2023.csv
OUTPUT  data/figures/fig_raw_comparison.json   (fetched by the component)

Run:  python data/scripts/10_fig_raw_comparison.py
"""

import json
import numpy as np
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_raw_comparison.json"

COUNTRIES = ["United States", "Indonesia", "Nigeria"]
SOURCES = {
    "WID_pretax_per_adult": "WID (pre-tax national income, per adult)",
    "WID_pretax_per_capita": "WID (pre-tax national income, per capita)",
    "WID_posttax_per_adult": "WID (post-tax national income, per adult)",
    "WID_posttax_per_capita": "WID (post-tax national income, per capita)",
    "PIP": "PIP (disposable income or consumption, per capita)",
}
ZERO_REPLACEMENT = 0.01  # $/day, applied ONLY inside the MLD calculation


def mld_decomposition(df):
    """Between/within MLD decomposition over the countries present in df.

    df columns: country, average (income $/day), pop (bin population).
    Returns dict with between, within, total and per-country details.
    """
    x = df["average"].to_numpy(dtype=float)
    w = df["pop"].to_numpy(dtype=float)
    country = df["country"].to_numpy()

    # Zero handling — documented convention, stated in the output meta.
    n_replaced = int((x == 0).sum())
    x = np.where(x == 0, ZERO_REPLACEMENT, x)

    total_pop = w.sum()
    mu = np.average(x, weights=w)

    within_total = 0.0
    between_total = 0.0
    details = []
    for c in COUNTRIES:
        m = country == c
        pop_c = w[m].sum()
        mu_c = np.average(x[m], weights=w[m])
        mld_c = np.average(np.log(mu_c / x[m]), weights=w[m])   # within-country MLD
        within_total += (pop_c / total_pop) * mld_c
        between_total += (pop_c / total_pop) * np.log(mu / mu_c)
        details.append({"country": c, "pop": pop_c, "mean": mu_c, "mld_within": mld_c})

    total = float(np.average(np.log(mu / x), weights=w))
    # Exact decomposition identity — if this trips, the code is wrong.
    assert abs(total - (within_total + between_total)) < 1e-9, \
        f"decomposition identity violated: {total} != {within_total} + {between_total}"

    return {
        "between": float(between_total),
        "within": float(within_total),
        "total": total,
        "between_share": float(between_total / total),
        "grand_mean": float(mu),
        "zero_bins_replaced": n_replaced,
        "countries": details,
    }


def main():
    h = pd.read_csv(HARMONIZED_FILE)

    lollipop = []
    mld = []
    for source, label in SOURCES.items():
        d = h[(h.source == source) & (h.country.isin(COUNTRIES))].copy()
        assert d.groupby("country").size().eq(109).all(), f"missing bins for {source}"

        for c in COUNTRIES:
            g = d[d.country == c]
            lollipop.append({
                "source": source,
                "country": c,
                "p10": float(g.loc[g.percentile == "p10p11", "average"].iloc[0]),
                "p90": float(g.loc[g.percentile == "p90p91", "average"].iloc[0]),
                "mean": float(np.average(g["average"], weights=g["pop"])),
            })

        res = mld_decomposition(d)
        res["source"] = source
        res["label"] = label
        mld.append(res)
        print(f"{source}: MLD total={res['total']:.3f}  "
              f"between={res['between']:.3f}  within={res['within']:.3f}  "
              f"(between share {res['between_share']:.1%}, "
              f"{res['zero_bins_replaced']} zero bins replaced)")

    out = {
        "meta": {
            "title": "Raw comparison: WID vs PIP, three countries, 2023",
            "countries": COUNTRIES,
            "sources": SOURCES,
            "year": 2023,
            "units": "international-$ per day (PIP: 2021 PPPs; WID: 2023 PPPs)",
            "zero_replacement_usd_per_day": ZERO_REPLACEMENT,
            "notes": [
                "Raw published concepts — no bridging adjustments applied.",
                "P10/P90 are the bin averages of p10p11 / p90p91.",
                "MLD computed on the full 109-bin distributions of the three "
                "countries only; zeros replaced with $0.01/day for the MLD only.",
                "WID weights are adults; PIP weights are total population.",
            ],
            "generated_by": "data/scripts/10_fig_raw_comparison.py",
        },
        "lollipop": lollipop,
        "mld": mld,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
