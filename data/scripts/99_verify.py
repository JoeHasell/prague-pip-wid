"""
99_verify.py — verification suite for the PIP/WID data pipeline.

Run this after any pipeline run (and after any future re-fetch of the raw
data). Every check prints PASS/FAIL and the script exits non-zero on any
failure, so it can gate a commit.

The checks encode the lessons from the original data project, where two
serious bugs were caught late:
  - incomes left in local currency (missing PPP conversion) — check 3
  - whole-country population used as bin weights — implicitly guarded by
    checks 5 and 6 (population totals and PIP mass conservation)

Run:  python data/scripts/99_verify.py
"""

import sys
import numpy as np
import pandas as pd

from config import (
    WID_PERCENTILES_RAW, WID_PPP_FILE, PIP_RAW_FILE,
    WID_PROCESSED_FILE, HARMONIZED_FILE, TARGET_YEAR, wid_bin_labels,
)

FAILURES = []


def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILURES.append(name)


def main():
    raw = pd.read_csv(WID_PERCENTILES_RAW)
    ppp = pd.read_csv(WID_PPP_FILE)
    pip = pd.read_csv(PIP_RAW_FILE)
    wid = pd.read_csv(WID_PROCESSED_FILE)
    h = pd.read_csv(HARMONIZED_FILE)
    labels = set(wid_bin_labels())

    # ------------------------------------------------------------------
    print("\n1. Raw WID structure")
    # ------------------------------------------------------------------
    bins = raw.groupby("country").size()
    check("211 countries x 109 bins", len(bins) == 211 and (bins == 109).all(),
          f"{len(bins)} countries, bins {bins.min()}-{bins.max()}")
    check("all bin labels match the canonical 109", set(raw["percentile"]) == labels)
    check(f"all rows are year {TARGET_YEAR}", (raw["year"] == TARGET_YEAR).all())
    widths = raw.assign(w=raw.p_high - raw.p_low).groupby("country")["w"].sum()
    check("bin widths sum to 1 per country", (widths.round(9) == 1).all())

    # ------------------------------------------------------------------
    print("\n2. Raw PIP structure")
    # ------------------------------------------------------------------
    pbins = pip.groupby("country").size()
    check("218 countries x 1000 bins", len(pbins) == 218 and (pbins == 1000).all())
    check("no missing/negative PIP incomes",
          pip["avg"].notna().all() and (pip["avg"] >= 0).all())

    # ------------------------------------------------------------------
    print("\n3. PPP conversion (site of the historical bug)")
    # ------------------------------------------------------------------
    # Recompute two spot values independently from raw + PPP and compare to
    # the processed file. US has PPP ~1 (would not catch the bug); Iran has
    # PPP ~92,000 (catches it loudly).
    def processed_value(country_code, percentile, col):
        r = wid[(wid.country_code == country_code) & (wid.percentile == percentile)]
        return float(r[col].iloc[0])

    def expected_per_adult(country_code, percentile, raw_col):
        v = float(raw.loc[(raw.country == country_code) &
                          (raw.percentile == percentile), raw_col].iloc[0])
        factor = float(ppp.loc[ppp.country == country_code, "ppp"].iloc[0])
        return v / factor / 365

    for code, pct, name in [("US", "p50p51", "US median"),
                            ("IR", "p99.9p100", "Iran top 0.1%"),
                            ("IN", "p0p1", "India bottom 1%")]:
        got = processed_value(code, pct, "avg_pretax_per_adult")
        exp = expected_per_adult(code, pct, "avg_pretax")
        check(f"{name} pre-tax/adult = {exp:,.2f} $/day",
              abs(got - exp) < 1e-6, f"processed: {got:,.2f}")
    # Sanity bounds that the local-currency bug would violate by orders of
    # magnitude (Iran top 0.1% was $199.8m/day when the bug was live):
    ir_top = processed_value("IR", "p99.9p100", "avg_pretax_per_adult")
    check("Iran top 0.1% within plausible range ($500-$20,000/day)",
          500 < ir_top < 20_000, f"{ir_top:,.2f}")

    # ------------------------------------------------------------------
    print("\n4. Income-concept identity (confirms diinc = post-tax NATIONAL income)")
    # ------------------------------------------------------------------
    # DINA post-tax national income redistributes all taxes & spending, so
    # each country's bin-width-weighted mean must equal the pre-tax mean.
    w = wid.assign(width=wid.p_high - wid.p_low)
    tot = w.groupby("country").apply(
        lambda d: pd.Series({
            "pre": (d.avg_pretax_per_adult * d.width).sum(),
            "post": (d.avg_posttax_per_adult * d.width).sum()}),
        include_groups=False)
    rel_gap = ((tot.post - tot.pre).abs() / tot.pre)
    check("post-tax total == pre-tax total in every country (tol 0.1%)",
          (rel_gap < 1e-3).all(), f"max gap {rel_gap.max():.2e}")

    # ------------------------------------------------------------------
    print("\n5. Per-adult -> per-capita adjustment")
    # ------------------------------------------------------------------
    nz = wid[wid.avg_pretax_per_adult > 0]
    ratio = nz.avg_pretax_per_capita / nz.avg_pretax_per_adult
    expected_ratio = nz.adult_pop / nz.total_pop
    check("per-capita / per-adult == adult share of population",
          np.allclose(ratio, expected_ratio),
          f"mean adult share {expected_ratio.mean():.3f}")

    # ------------------------------------------------------------------
    print("\n6. Harmonized dataset")
    # ------------------------------------------------------------------
    counts = h.groupby(["source", "country"]).size()
    check("109 bins per country in every series", (counts == 109).all(),
          f"min {counts.min()}, max {counts.max()}")
    check("bin labels identical across all sources",
          all(set(g["percentile"]) == labels for _, g in h.groupby("source")))

    # PIP mass conservation: aggregation must preserve each country's total
    # income and population exactly (it is a pure regrouping of bins).
    pip_tot_raw = pip.assign(inc=pip["avg"] * pip["pop"]).groupby("country")[["inc", "pop"]].sum()
    hp = h[h.source == "PIP"]
    pip_tot_h = hp.assign(inc=hp.average * hp["pop"]).groupby("country")[["inc", "pop"]].sum()
    aligned = pip_tot_raw.join(pip_tot_h, lsuffix="_raw", rsuffix="_h")
    check("PIP aggregation conserves total income per country",
          np.allclose(aligned.inc_raw, aligned.inc_h, rtol=1e-9))
    check("PIP aggregation conserves population per country",
          np.allclose(aligned.pop_raw, aligned.pop_h, rtol=1e-9))

    # Shares should sum to ~1 within each country-series (WID shares come
    # from the API with ~4 decimals, so tolerance is loose there).
    ssum = h.groupby(["source", "country"])["share"].sum()
    check("income shares sum to 1 (tol 0.5%)",
          ((ssum - 1).abs() < 5e-3).all(), f"max dev {(ssum - 1).abs().max():.4f}")

    # Population totals per series: per-capita series should carry each
    # country's total population, per-adult series the adult population.
    wpop = wid.groupby("country")[["adult_pop", "total_pop"]].first()
    for src, col in [("WID_pretax_per_capita", "total_pop"),
                     ("WID_pretax_per_adult", "adult_pop")]:
        got = h[h.source == src].groupby("country")["pop"].sum()
        check(f"{src} pop sums to {col}",
              np.allclose(got, wpop.loc[got.index, col], rtol=1e-6))

    # Zeros are documented, not dropped: every zero-income bin in the raw
    # data must survive into the harmonized file (dropping zeros silently
    # would bias MLD later). Compared against the raw file, not a hardcoded
    # count, so this stays valid across data refreshes.
    n_zero_raw = int((raw["avg_pretax"] == 0).sum())
    n_zero_h = int((h[h.source == "WID_pretax_per_adult"]["average"] == 0).sum())
    check("zero incomes retained in harmonized data (== raw count)",
          n_zero_h == n_zero_raw, f"raw {n_zero_raw}, harmonized {n_zero_h}")

    # ------------------------------------------------------------------
    print("\n7. Cross-source coverage")
    # ------------------------------------------------------------------
    pip_countries = set(h.loc[h.source == "PIP", "country"])
    wid_countries = set(h.loc[h.source == "WID_pretax_per_adult", "country"])
    both = pip_countries & wid_countries
    check("every WID country matches a PIP country name",
          wid_countries <= pip_countries,
          f"unmatched: {sorted(wid_countries - pip_countries) or 'none'}")
    print(f"         coverage: PIP {len(pip_countries)}, WID {len(wid_countries)}, "
          f"overlap {len(both)}")

    # ------------------------------------------------------------------
    print()
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED: {FAILURES}")
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    main()
