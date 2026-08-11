"""
15_fig_top_thresholds.py — data for the deck figure "fig-top-thresholds".

THE FIGURE (rendered by components/fig-top-thresholds.js)
----------------------------------------------------------
Q3: who are the richest 1%? Before looking at WHO is in the global top
groups, this figure compares the ENTRY INCOME — the income level that puts
you in the global top 10% / top 1% / top 0.1% — across the seven scenarios
of the Q2 bridging charts, over the same 211-country common sample.

METHOD
------
For each scenario, pool every country-bin of the common sample, sort by bin
average income (descending) and accumulate population until the target share
of the GLOBAL population is reached. The threshold reported is the average
income of the MARGINAL bin — the bin in which the cumulative population
crosses the target. With 109 bins per country this bin is at most 1% of one
country's population wide, so the approximation is tight.

POPULATION CONCEPT (basis-matched, per the project convention — mld.py):
  - per-adult series: the top X% OF THE WORLD'S ADULTS, weights = WID adult
    populations;
  - per-capita series (incl. PIP and all derived series): the top X% of ALL
    people, weights = WID total populations.
Each scenario is an internally coherent object; the sources' demographic
disagreements never enter (PIP is weighted by WID demography too).

INPUT   data/processed/pip_wid_harmonized_2023.csv
OUTPUT  data/figures/fig_top_thresholds.json

Run:  python data/scripts/15_fig_top_thresholds.py
"""

import json
import pandas as pd

from config import HARMONIZED_FILE, DATA_DIR, DAILY_TO_MONTHLY
from mld import reference_populations
from scenarios import DISPLAY_SCENARIOS, common_sample, append_derived

FIGURES_DIR = DATA_DIR / "figures"
OUTPUT_FILE = FIGURES_DIR / "fig_top_thresholds.json"

TOP_SHARES = [0.10, 0.01, 0.001]   # top 10%, top 1%, top 0.1%


def entry_income(d, share):
    """The average income of the marginal bin for the global top `share`.

    d must have columns income (bin average) and w (bin population under the
    scenario's basis-matched weights)."""
    d = d.sort_values("income", ascending=False)
    target = d["w"].sum() * share
    cum = d["w"].cumsum()
    # The marginal bin: the first bin at which the cumulative population
    # reaches the target.
    return float(d.loc[cum >= target - 1e-9, "income"].iloc[0])


def main():
    h = pd.read_csv(HARMONIZED_FILE)
    countries = common_sample(h)
    h, rep = append_derived(h, countries)
    print(f"{len(countries)} countries; consinc: "
          f"{rep['consumption_adjusted']} adjusted, "
          f"{rep['income_passthrough']} pass-through")

    results = []
    for sc in DISPLAY_SCENARIOS:
        src, basis = sc["source"], sc["basis"]
        ref_pop = reference_populations(h, "wid", basis)
        d = h[(h.source == src) & (h.country.isin(countries))].copy()
        assert d.groupby("country").size().eq(109).all(), f"missing bins for {src}"
        d["w"] = d["country"].map(ref_pop) * (d["p_high"] - d["p_low"])
        d = d.rename(columns={"average": "income"})

        row = {"source": src, "label": sc["label"], "basis": basis}
        for share in TOP_SHARES:
            key = f"top{share * 100:g}".replace(".", "_")   # top10, top1, top0_1
            # Displayed values are PER MONTH (config.DAILY_TO_MONTHLY); the
            # ranking itself happens on the daily values (scale-invariant).
            row[key] = round(entry_income(d, share) * DAILY_TO_MONTHLY, 2)
        results.append(row)
        print(f"{src:26s} top10 ${row['top10']:>9,.2f}  "
              f"top1 ${row['top1']:>10,.2f}  top0.1 ${row['top0_1']:>11,.2f}")

    out = {
        "meta": {
            "title": "What income puts you in the global top 10% / 1% / 0.1%?",
            "top_shares": TOP_SHARES,
            "n_countries": len(countries),
            "year": 2023,
            "units": "international-$ PER MONTH (PIP: 2021 PPPs; WID: 2023 "
                     "PPPs); converted from daily values at 365/12",
            "notes": [
                "Thresholds are ENTRY incomes: the average income of the "
                "marginal country-bin when bins are sorted by income and "
                "population is accumulated to the target global share.",
                "Population concept is basis-matched (mld.py convention): "
                "per-adult series rank the world's ADULTS (WID adult "
                "populations); per-capita series rank all people (WID total "
                "populations).",
                "Computed over the common sample of countries present in "
                "both PIP and WID.",
            ],
            "generated_by": "data/scripts/15_fig_top_thresholds.py",
        },
        "thresholds": results,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
