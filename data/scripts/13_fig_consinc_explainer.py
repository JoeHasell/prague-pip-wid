"""
13_fig_consinc_explainer.py — data for the deck figure "fig-consinc-explainer".

THE FIGURE (rendered by components/fig-consinc-explainer.js)
-------------------------------------------------------------
For a selectable consumption-based country: the PIP consumption distribution
(income by percentile, log scale) with the regression-PREDICTED income
distribution overlaid — and, for the dual countries that also publish an
actual income distribution, the ACTUAL income series too, so the chart
doubles as an in-sample fit check (default country: Albania, a dual one).

Everything is computed at the PIP percentiles table's native 100-bin
resolution, at each country's MOST RECENT national consumption year (so the
year varies by country and is shown in the chart). The regression is the one
fitted by 04_fit_consinc.py; the method module is consinc.py.

INPUTS  OWID catalog percentiles table (network) + processed/consinc_model.csv
OUTPUT  data/figures/fig_consinc_explainer.json

Run:  python data/scripts/13_fig_consinc_explainer.py
"""

import json
import numpy as np
import pandas as pd

from config import DATA_DIR, PROCESSED_DIR, DAILY_TO_MONTHLY

PERCENTILES_URL = ("https://catalog.ourworldindata.org/garden/wb/2026-06-26/"
                   "world_bank_pip/percentiles.parquet")
FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_consinc_explainer.json"


def sig4(x):
    # Displayed values are PER MONTH (config.DAILY_TO_MONTHLY). The model is
    # fitted (and applied) on DAILY values — its alpha is unit-specific — so
    # the conversion happens strictly after prediction, for display only.
    return float(f"{x * DAILY_TO_MONTHLY:.4g}")


# Superseded by the ETL pipeline — see legacy_guard.py.
from legacy_guard import require_ack


def main():
    require_ack(
        script='13_fig_consinc_explainer.py',
        figures=['fig_consinc_explainer.json'],
        replaced_by='23_fig_explainers_from_etl.py',
    )
    model = pd.read_csv(PROCESSED_DIR / "consinc_model.csv")
    alpha = model.set_index("percentile")["alpha"]
    beta = model.set_index("percentile")["beta"]

    df = pd.read_parquet(PERCENTILES_URL, columns=[
        "country", "year", "ppp_version", "welfare_type",
        "reporting_level", "percentile", "avg"])
    d = df[(df.ppp_version == 2021) & (df.reporting_level == "national")
           & df.welfare_type.isin(["income", "consumption"])]

    # Year shown per country: the most recent year with BOTH series if the
    # country has one (so the fit check displays), else the most recent
    # consumption year.
    cons = d[d.welfare_type == "consumption"]
    latest_cons = cons.groupby("country")["year"].max()
    k = d.groupby(["country", "year"])["welfare_type"].nunique()
    dual_latest = (k[k == 2].reset_index().groupby("country")["year"].max())
    latest = latest_cons.copy()
    latest.update(dual_latest)

    countries = {}
    n_dual = 0
    for c, yr in latest.items():
        g = d[(d.country == c) & (d.year == yr)]
        cvals = (g[g.welfare_type == "consumption"]
                 .sort_values("percentile")["avg"].to_numpy(dtype=float))
        if len(cvals) != 100 or (cvals <= 0).any():
            continue
        pred = np.exp(alpha.loc[range(1, 101)].to_numpy()) * \
            cvals ** beta.loc[range(1, 101)].to_numpy()
        entry = {
            "year": int(yr),
            "cons": [sig4(v) for v in cvals],
            "pred": [sig4(v) for v in pred],
        }
        inc = g[g.welfare_type == "income"].sort_values("percentile")["avg"]
        if len(inc) == 100:
            entry["inc"] = [sig4(v) for v in inc.to_numpy(dtype=float)]
            n_dual += 1
        countries[c] = entry

    print(f"{len(countries)} consumption countries "
          f"({n_dual} with an actual income series for the same year)")

    out = {
        "meta": {
            "title": "Consumption → income: the fitted mapping, country by country",
            "default_country": "Albania" if "Albania" in countries else sorted(countries)[0],
            "units": "international-$ per month, 2021 PPPs (converted from "
                     "daily at 365/12; the model itself is fitted on daily values)",
            "model": "ln y_p = alpha_p + beta_p ln c_p, fitted per percentile "
                     "on 88 dual country-years (04_fit_consinc.py)",
            "notes": [
                "Each country shown at its most recent national consumption "
                "year (varies by country; shown in the chart).",
                "For dual countries the actual income series is included — "
                "an in-sample fit check.",
            ],
            "generated_by": "data/scripts/13_fig_consinc_explainer.py",
        },
        "countries": countries,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, separators=(",", ":")))
    print(f"Saved: {OUTPUT_FILE} ({OUTPUT_FILE.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
