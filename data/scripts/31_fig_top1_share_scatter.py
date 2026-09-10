"""
31_fig_top1_share_scatter.py — the top-1% income share, country by country,
under each PIP-side series and under WID post-tax.

WHY
---
The bridging figure and the sensitivity table both report GLOBAL decompositions,
so they cannot show which countries the PIP-side adjustments actually move, or
how close any of them gets to WID's own view of the top. The top-1% share is the
natural quantity for that: it is the thing the adjustments are trying to fix, it
is scale-free, and WID publishes something directly comparable.

One point per country per series, plotted against the same country's WID post-tax
share, so the 45-degree line is agreement.

SERIES SHOWN
------------
  PIP                    as published (mixed income/consumption)
  PIP_consinc            after the consumption -> income profile
  PIP_append             + the survey re-read as the bottom 99%, WID's top appended
  WID_posttax_per_capita the comparison axis

INPUT   data/raw/etl/display_year_bins.csv.gz  (via etl_source.load_bins)
        data/raw/etl/treemap_regions.csv.gz
OUTPUT  data/figures/fig_top1_share_scatter.json

Run:  python data/scripts/31_fig_top1_share_scatter.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import etl_source as es
import topadj

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
OUT_FILE = FIGURES_DIR / "fig_top1_share_scatter.json"

TOP1 = ("p99p99.1", "p99.1p99.2", "p99.2p99.3", "p99.3p99.4", "p99.4p99.5",
        "p99.5p99.6", "p99.6p99.7", "p99.7p99.8", "p99.8p99.9", "p99.9p100")
WID = "WID_posttax_per_capita"
PIP_SERIES = [
    ("PIP", "PIP, as published"),
    ("PIP_consinc", "PIP on an income basis"),
    ("PIP_append", "+ WID's top 1% appended"),
]


def top1_share(bins, series, year):
    """Each country's share of total income going to its top 1% (percent)."""
    d = bins[(bins["series"] == series) & (bins["year"] == year)]
    assert len(d), f"no {series} rows for {year}"
    inc = d["avg"].to_numpy(float) * d["pop"].to_numpy(float)
    # Select the top 1% by RANK, not by bin label: the appended series collapses
    # the ten 0.1% labels into one "p99p100" bin, so a label test silently
    # returns a zero share for it.
    t = pd.DataFrame({"country": d["country"].to_numpy(),
                      "inc": inc,
                      "top": (d["p_low"].to_numpy(float) >= topadj.TOP1_START - 1e-9)})
    g = t.groupby("country", observed=True)
    return 100.0 * g.apply(lambda x: x.loc[x["top"], "inc"].sum() / x["inc"].sum())


def main():
    year = es.DISPLAY_YEAR
    bins = es.load_bins("display_year_bins")
    bins = bins[bins["year"] == year]
    # Both top-1% methods, built here so the figure can show them side by side.
    # The deck's own PIP_topadj is whichever of the two etl_source names; it is
    # rebuilt rather than read so the two are guaranteed to share a base.
    for key, method in (("PIP_append", "append"),):
        bins = pd.concat([bins, topadj.build_top1(bins, method, out_series=key,
                                                  grid=(method == "match"))],
                         ignore_index=True)

    regions = es.load("treemap_regions").set_index("country")["region"]
    pop = (bins[bins["series"] == WID].groupby("country", observed=True)["pop"].sum())
    wid = top1_share(bins, WID, year)
    shares = {k: top1_share(bins, k, year) for k, _ in PIP_SERIES}

    common = wid.index
    for v in shares.values():
        common = common.intersection(v.index)
    common = sorted(common.intersection(pop.index))
    print(f"  {len(common)} countries")

    region_order = sorted(set(regions.reindex(common).fillna("Other")))
    ridx = {r: i for i, r in enumerate(region_order)}
    countries = [{"c": c,
                  "r": ridx[regions.get(c, "Other")],
                  "pop": int(pop[c]),
                  "wid": round(float(wid[c]), 3),
                  "pip": {k: round(float(shares[k][c]), 3) for k, _ in PIP_SERIES}}
                 for c in common]

    for k, lab in PIP_SERIES:
        s = shares[k].reindex(common)
        d = (s - wid.reindex(common))
        print("  %-32s median %5.1f%%  (WID %5.1f%%)  median gap %+5.1fpp  above WID: %d"
              % (lab, s.median(), wid.reindex(common).median(), d.median(), int((d > 0).sum())))

    out = {
        "meta": {
            "title": "Top 1% income share: each PIP series against WID post-tax",
            "year": year,
            "n_countries": len(common),
            "units": "share of each country's total income going to its top 1%, in percent",
            "series": [{"key": k, "label": lab} for k, lab in PIP_SERIES],
            "wid_label": "WID post-tax national income, per capita",
            "default_series": "PIP_append",
            "notes": [
                "The 45-degree line is agreement between the two sources.",
                "Bubble area is proportional to population; colour is region.",
                "The top-1% adjustment shown here re-reads the survey as the bottom "
                "99% and appends WID's top percentile; it is not applied where WID's "
                "top-1% share is not above PIP's. By construction the adjusted series "
                "then sits on the 45-degree line wherever it was applied.",
                "Shares are computed from the same 100-percentile distributions as the "
                "decomposition, so they carry the same conventions (WID bottom-coded at "
                "1% of country mean; PIP as the World Bank publishes it).",
            ],
            "generated_by": "data/scripts/31_fig_top1_share_scatter.py",
        },
        "regions": region_order,
        "countries": countries,
    }
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"Saved: {OUT_FILE.name} ({OUT_FILE.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
