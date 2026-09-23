"""
39_adjustment_effects.py — what each PIP adjustment does on its own, and together, at the 2022
reference year.

    data/processed/adjustment_effects.csv        one row per country: the measures on each series
    data/figures/fig_adjustment_effects.json     the averages and ranges the Prague slides quote

WHAT IT IS
----------
The deck's chain applies two adjustments in a row: consumption -> income (PIP_consinc), then
WID's top 1% appended on top of that (PIP_topadj). Their effects are therefore mixed. This script
adds the missing piece, the top-1% adjustment ALONE: the same append (topadj.build_top1, the same
method and gate as the chain) applied directly to PIP as published, before any consumption ->
income step. It is called PIP_top1only here and lives only in this file — it is not part of the
bridging chain.

For every country with a national PIP survey within five years of 2022 (the nearest survey,
either side, as in the Prague slides' maps and Marimekkos), it reports the Gini, top-10% share
and top-1% share of:

    PIP            PIP as published
    PIP_top1only   PIP with WID's top 1% appended, no consumption -> income step
    PIP_consinc    PIP on an income basis (the deck's WID profile), no top adjustment
    PIP_topadj     both: the deck's chain

and the change each step makes relative to PIP.

HOW TO READ THE TOP-1%-ONLY SERIES
----------------------------------
- For CONSUMPTION countries it appends WID's top-1% share of post-tax INCOME to a CONSUMPTION
  distribution: two concepts in one distribution. That is the point of the exercise — it isolates
  the top adjustment — but the level is not an estimate of anything a survey could measure.
- The gate is decided on PIP itself (append only where WID's top-1% share exceeds PIP's own), so
  it can differ from the chain's gate, which is decided on PIP_consinc.
- The top-1% share comes from WID at the PIP survey year, like the chain.

INPUTS: the ETL cache (reference_year_bins, pip_welfare_basis) through etl_source.load_bins, and
data/processed/reference_year_indicators.csv (33_) for the 2022 reference-year match.

Run:  python data/scripts/39_adjustment_effects.py   (after 33_)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es
import refyears
import topadj

DATA_DIR = Path(__file__).resolve().parents[1]
REFYEAR_FILE = DATA_DIR / "processed" / "reference_year_indicators.csv"
OUT_FILE = DATA_DIR / "processed" / "adjustment_effects.csv"
FIG_FILE = DATA_DIR / "figures" / "fig_adjustment_effects.json"

REF_YEAR = 2022
SERIES = ["PIP", "PIP_top1only", "PIP_consinc", "PIP_topadj"]
MEASURES = ["gini", "top10_share", "top1_share"]
# What each step is compared with, for the summary.
STEPS = {
    "top1only": ("PIP", "PIP_top1only", "Top 1% adjustment alone"),
    "consinc": ("PIP", "PIP_consinc", "Consumption -> income alone"),
    "both": ("PIP", "PIP_topadj", "Both adjustments"),
}


def main():
    ref = pd.read_csv(REFYEAR_FILE)
    sample = ref[(ref["series"] == "PIP") & (ref["ref_year"] == REF_YEAR)][["country", "year", "welfare_type"]]
    print(f"{len(sample)} countries with a national PIP survey within five years of {REF_YEAR}")

    bins = es.load_bins("reference_year_bins")
    keys = set(zip(sample["country"], sample["year"]))
    bins = bins[[k in keys for k in zip(bins["country"], bins["year"])]]

    # The top-1% append on PIP itself, year by year (the gate and shares are per country-year).
    alone, gates = [], []
    for y, gy in bins.groupby("year"):
        base = gy[gy["series"].isin(["PIP", topadj.WID_SHAPE_SOURCE])]
        alone.append(topadj.build_top1(base, es.TOPADJ_METHOD, base_series="PIP", out_series="PIP_top1only"))
        g = topadj.top1_shares(base, "PIP").reset_index()
        g["year"] = y
        gates.append(g)
    alone = pd.concat(alone, ignore_index=True)
    gate = pd.concat(gates, ignore_index=True)[["country", "year", "adjust"]].rename(columns={"adjust": "top1_adjusted"})

    ind = refyears.indicators_from_bins(pd.concat([bins[bins["series"].isin(SERIES)], alone], ignore_index=True))
    wide = ind.pivot_table(index=["country", "year"], columns="series", values=MEASURES)
    wide.columns = [f"{m}__{s}" for m, s in wide.columns]
    out = sample.merge(wide.reset_index(), on=["country", "year"], how="left").merge(gate, on=["country", "year"], how="left")
    assert out[[f"{m}__{s}" for m in MEASURES for s in SERIES]].notna().all().all(), "a country lacks a series"
    assert len(out) == len(sample)

    # Sanity: the top-1% step leaves unadjusted countries exactly as they were, and never lowers the top share.
    same = out.loc[~out["top1_adjusted"], "gini__PIP_top1only"] - out.loc[~out["top1_adjusted"], "gini__PIP"]
    assert np.allclose(same, 0, atol=1e-9), "the gate should pass unadjusted countries through"
    assert (out["top1_share__PIP_top1only"] >= out["top1_share__PIP"] - 1e-9).all(), "the append lowered a top share"

    out = out.rename(columns={"year": "survey_year"}).sort_values("country")
    out.to_csv(OUT_FILE, index=False, float_format="%.6g")
    print(f"Saved: {OUT_FILE.relative_to(DATA_DIR.parent)} ({len(out)} rows)")

    fig = {"meta": {"ref_year": REF_YEAR, "n_countries": len(out),
                    "n_consumption": int((out["welfare_type"] == "consumption").sum()),
                    "n_top1_adjusted": int(out["top1_adjusted"].sum()),
                    "generated_by": "39_adjustment_effects.py"},
           "steps": {}}
    for key, (a, b, label) in STEPS.items():
        g = out[f"gini__{b}"] / out[f"gini__{a}"] - 1
        t10 = out[f"top10_share__{b}"] - out[f"top10_share__{a}"]
        t1 = out[f"top1_share__{b}"] - out[f"top1_share__{a}"]
        fig["steps"][key] = {
            "label": label,
            "gini_pct_mean": round(100 * float(g.mean()), 1), "gini_pct_min": round(100 * float(g.min()), 1),
            "gini_pct_max": round(100 * float(g.max()), 1),
            "gini_mean_before": round(float(out[f"gini__{a}"].mean()), 3), "gini_mean_after": round(float(out[f"gini__{b}"].mean()), 3),
            "top10_pts_mean": round(float(t10.mean()), 1), "top10_pts_min": round(float(t10.min()), 1), "top10_pts_max": round(float(t10.max()), 1),
            "top1_pts_mean": round(float(t1.mean()), 1),
            "top1_mean_before": round(float(out[f"top1_share__{a}"].mean()), 1), "top1_mean_after": round(float(out[f"top1_share__{b}"].mean()), 1),
            "n_changed": int((g.abs() > 1e-9).sum()),
        }
    FIG_FILE.write_text(json.dumps(fig, indent=1))
    print(f"Saved: {FIG_FILE.relative_to(DATA_DIR.parent)}")
    print(json.dumps(fig, indent=1))


if __name__ == "__main__":
    main()
