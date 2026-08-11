"""
04_fit_consinc.py — fit the consumption -> income mapping from PIP's dual
country-years, and record which PIP countries are consumption-based.

WHY
---
PIP's headline series mixes income countries and consumption countries.
To put them on a common (income) basis, we estimate how income distributions
relate to consumption distributions using the country-years where PIP
publishes BOTH (88 national country-years at 2021 PPPs, 19 countries —
Europe-heavy plus the Philippines, Nicaragua, Haiti, Saint Lucia; NOTE the
transfer caveat: no Sub-Saharan Africa or South Asia in the sample).

THE MODEL (chosen 2026-08-11; "approach B")
-------------------------------------------
One OLS regression PER PERCENTILE BIN p = 1..100, across the dual pairs:

    ln y_p  =  alpha_p  +  beta_p * ln c_p  +  e

where y_p / c_p are the income / consumption bin averages ($/day, 2021 PPP,
per capita) of percentile bin p. The fitted mapping applied to a
consumption-only distribution is

    y_hat_p = exp(alpha_p) * c_p ** beta_p .

Notes:
  - beta_p != 1 lets the twist depend on the consumption level.
  - No smoothing is applied to the coefficient curves unless they come out
    jagged — the script prints diagnostics; see the saved CSV.
  - Applying the model to the deck's 109-bin structure: bins 1-99 map 1:1 to
    the fit's 1%-bins; the ten 0.1% bins inside the top 1% all use the
    p=100 coefficients (the within-top structure is carried by each
    sub-bin's own c value). See consinc.py.

DATA SOURCE (verified 2026-08-11 to match our thousand-bins data to 0.01%):
    garden/wb/2026-06-26/world_bank_pip/percentiles  (OWID catalog)

OUTPUTS
-------
data/processed/consinc_model.csv        percentile, alpha, beta, n, r2
data/raw/pip/pip_welfare_types.csv      country, welfare_type, year_of_info
    welfare_type = type of the country's most recent national observation in
    the percentiles table; countries whose latest year has BOTH types are
    recorded as "income" (no adjustment needed — PIP prefers income where
    both exist). The deck's PIP rows are 2023 line-ups, so this is the best
    available proxy for which welfare concept underlies each country's row.

Run:  python data/scripts/04_fit_consinc.py     (network: OWID catalog)
"""

import numpy as np
import pandas as pd

from config import RAW_PIP_DIR, PROCESSED_DIR

PERCENTILES_URL = ("https://catalog.ourworldindata.org/garden/wb/2026-06-26/"
                   "world_bank_pip/percentiles.parquet")
MODEL_FILE = PROCESSED_DIR / "consinc_model.csv"
WELFARE_FILE = RAW_PIP_DIR / "pip_welfare_types.csv"


def main():
    print(f"Loading PIP percentiles from OWID catalog…")
    df = pd.read_parquet(PERCENTILES_URL, columns=[
        "country", "year", "ppp_version", "welfare_type",
        "reporting_level", "percentile", "avg"])
    d = df[(df.ppp_version == 2021) & (df.reporting_level == "national")
           & df.welfare_type.isin(["income", "consumption"])].copy()

    # ------------------------------------------------------------------
    # 1. The estimation sample: country-years with BOTH welfare types
    # ------------------------------------------------------------------
    k = d.groupby(["country", "year"])["welfare_type"].nunique()
    dual = k[k == 2].index
    sample = d.set_index(["country", "year"]).loc[dual].reset_index()
    piv = sample.pivot_table(index=["country", "year", "percentile"],
                             columns="welfare_type", values="avg").reset_index().dropna()
    piv = piv[(piv.income > 0) & (piv.consumption > 0)]
    n_cy = len(dual)
    print(f"estimation sample: {n_cy} dual country-years, "
          f"{piv.country.nunique()} countries, {len(piv):,} percentile pairs")

    # ------------------------------------------------------------------
    # 2. Per-percentile OLS:  ln y = alpha_p + beta_p ln c
    # ------------------------------------------------------------------
    rows = []
    for p, g in piv.groupby("percentile"):
        x = np.log(g["consumption"].to_numpy(dtype=float))
        y = np.log(g["income"].to_numpy(dtype=float))
        beta, alpha = np.polyfit(x, y, 1)
        resid = y - (alpha + beta * x)
        r2 = 1 - resid.var() / y.var()
        rows.append({"percentile": int(p), "alpha": alpha, "beta": beta,
                     "n": len(g), "r2": r2})
    model = pd.DataFrame(rows).sort_values("percentile")

    # Diagnostics: are the coefficient curves smooth enough to use raw?
    rough_b = model["beta"].diff().abs().median()
    print(f"\ncoefficients: beta range [{model.beta.min():.3f}, {model.beta.max():.3f}], "
          f"median |Δbeta| between adjacent percentiles {rough_b:.4f}")
    print(f"R² range [{model.r2.min():.3f}, {model.r2.max():.3f}], median {model.r2.median():.3f}")
    for p in [1, 5, 25, 50, 75, 95, 100]:
        r = model[model.percentile == p].iloc[0]
        print(f"  p{p:>3}: alpha={r.alpha:+.3f}  beta={r.beta:.3f}  R²={r.r2:.3f}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    model.to_csv(MODEL_FILE, index=False)
    print(f"Saved: {MODEL_FILE}")

    # ------------------------------------------------------------------
    # 3. Welfare-type lookup: each country's most recent national type
    # ------------------------------------------------------------------
    latest = d.groupby("country")["year"].max().rename("year_of_info")
    last = d.merge(latest, left_on=["country", "year"], right_on=["country", "year_of_info"])
    types = last.groupby("country")["welfare_type"].agg(lambda s: sorted(set(s)))
    lookup = pd.DataFrame({
        "country": types.index,
        # both types in the latest year -> income (no adjustment)
        "welfare_type": ["income" if ("income" in t) else "consumption" for t in types],
        "year_of_info": latest.loc[types.index].values,
    })
    lookup.to_csv(WELFARE_FILE, index=False)
    n_cons = (lookup.welfare_type == "consumption").sum()
    print(f"Saved: {WELFARE_FILE} — {len(lookup)} countries, "
          f"{n_cons} consumption-based, {len(lookup) - n_cons} income-based")
    for c in ["United States", "Indonesia", "Nigeria"]:
        row = lookup[lookup.country == c]
        print("  ", c, "->", row.welfare_type.iloc[0] if len(row) else "NOT IN LOOKUP")


if __name__ == "__main__":
    main()
