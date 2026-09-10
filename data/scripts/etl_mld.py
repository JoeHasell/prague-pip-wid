"""
etl_mld.py — between/within MLD decomposition computed from the ETL's BINS.

WHY THIS EXISTS
---------------
The ETL publishes ready-made decompositions (`inequality_decomposition`,
`inequality_decomposition_by_country`), and the deck read them directly until
2026-09-08. They bake in one zero-income convention: replace zeros with
$0.01/day, touch nothing else.

That convention turned out to dominate the WID numbers. WID's pre-tax series
reports exactly zero income for the bottom 5% in 184 of 211 countries (DINA
allocates zero rather than dropping people), and at $0.01/day those bins supply
a MEDIAN 43.5% of each country's within-MLD. Symptoms: an artificial floor of
about 0.7 on WID within-MLD, and the United States — one of only 26 countries
with no zero bins, hence the only ones measured on their own merits — ranking
37th of 44 on within-MLD against 12th on WID's own published Gini.

So the decomposition is recomputed here, from the same bins the ETL used, under
a stated floor. The floor rule itself lives in mld.py (`country_floor`), so the
local pipeline and this ETL path cannot drift apart on the definition.

WHAT IT REPRODUCES
------------------
Called with floor_rule=None this reproduces the ETL's published numbers exactly
— that is the regression test in `main()`, and it is the reason to trust the
switched-on version.

WEIGHTS: countries are weighted by ONE demographic yardstick, matched to the
series' basis. In the ETL that yardstick is independent of both sources — OWID's
population series for total population, UN WPP adults 20+ for per-adult series —
and it is the population carried on the WID series' bins, which is why those are
read here as the reference. PIP's bins carry PIP's OWN populations, which differ
from the yardstick by more than 1% for 34 of 200 countries; weighting by them
instead reproduces the ETL only to 5e-04 rather than 6e-08. Within-country bin
shares are unaffected either way (every bin of a country carries the same
population), so the choice matters only for the cross-country aggregation.

Run:  python data/scripts/etl_mld.py        # regression test + the deck's numbers
"""

import numpy as np
import pandas as pd

from mld import country_floor

# Series whose zero bins are a DINA modelling choice rather than observation.
# PIP arrives bottom-coded at $0.28/day by the World Bank and is left alone.
WID_SERIES = (
    "WID_pretax_per_adult", "WID_pretax_per_capita",
    "WID_posttax_per_adult", "WID_posttax_per_capita",
    "WID_posttax_rescaled",
)

# THE deck's convention, from 2026-09-08: bottom-code WID at 1% of each
# country's own raw mean (LIS practice). See data/README.md.
DECK_FLOOR_RULE = ("mean_fraction", 0.01)


def floor_for(series):
    """The floor rule this project applies to `series` (None = zeros->$0.01)."""
    return DECK_FLOOR_RULE if series in WID_SERIES else None


def decompose(bins, series, year, floor_rule="deck", zero_replacement=0.01,
              expect_bins=100):
    """Between/within MLD of one series in one year, from ETL bins.

    floor_rule: "deck" -> floor_for(series); None -> the ETL's own convention
    (replace zeros with `zero_replacement`); or an explicit (kind, value) pair.

    expect_bins: the bin count every country must have. 100 is the deck's grid
    since 2026-09-09 (etl_source.DECK_BINS), so every caller reading load_bins()
    keeps the guard for free. Pass another
    count only for a series that deliberately sits off the grid — the Anand-Segal
    top adjustment appends a top group to the survey rather than replacing bins.
    Pass None to skip the check entirely, which is needed only when a series
    leaves SOME countries untouched and so is ragged by construction. The guard
    exists because a country silently missing bins would quietly bias its mean,
    so switch it off only when the raggedness is the intended result.
    """
    if floor_rule == "deck":
        floor_rule = floor_for(series)

    d = bins[(bins.series == series) & (bins.year == year)]
    assert len(d), f"no {series} bins for {year}"
    # One demographic yardstick for country weights, matched to the series'
    # basis. It rides on the WID series' bins (see WEIGHTS in the docstring).
    ref_series = "WID_pretax_per_adult" if "per_adult" in series else "WID_pretax_per_capita"
    ref_pop = (bins[(bins.series == ref_series) & (bins.year == year)]
               .groupby("country", observed=True)["pop"].sum())
    n = d.groupby("country").size()
    if expect_bins is not None:
        assert (n == expect_bins).all(), \
            f"incomplete bins for {series} {year}: {n[n != expect_bins].to_dict()}"
    assert (n > 0).all(), f"empty bins for {series} {year}"

    coded, means, pops, n_coded, n_zero = {}, {}, {}, 0, 0
    missing = sorted(set(d.country.unique()) - set(ref_pop.index))
    assert not missing, f"no {ref_series} population for: {missing[:5]}"
    for c, g in d.groupby("country", observed=True):
        x = g.avg.to_numpy(dtype=float)
        w = g["pop"].to_numpy(dtype=float)
        n_zero += int((x == 0).sum())
        if floor_rule is None:
            x = np.where(x == 0, zero_replacement, x)
            n_coded += int((g.avg.to_numpy() == 0).sum())
        else:
            f = country_floor(x, w, floor_rule)      # raw mean, before coding
            n_coded += int((x < f).sum())
            x = np.maximum(x, f)
        coded[c], means[c] = (x, w), float(np.average(x, weights=w))
        pops[c] = float(ref_pop[c])          # the yardstick, not the series' own

    cm = pd.Series(means)
    share = pd.Series(pops) / sum(pops.values())
    mu = float((share * cm).sum())

    within = float(sum(share[c] * np.average(np.log(means[c] / x), weights=w)
                       for c, (x, w) in coded.items()))
    between = float((share * np.log(mu / cm)).sum())
    return {
        "series": series, "year": int(year),
        "within": within, "between": between, "total": within + between,
        "between_share": between / (within + between),
        "grand_mean": mu, "num_countries": len(cm),
        "num_zero_bins": n_zero, "num_bins_coded": n_coded,
        "floor_rule": floor_rule,
        "by_country": pd.DataFrame({
            "mean": cm,
            "mld_within": {c: float(np.average(np.log(means[c] / x), weights=w))
                           for c, (x, w) in coded.items()},
            "population_weight": pd.Series(pops),
        }),
    }


def main():
    import etl_source as es
    bins = es.load("display_year_bins")
    published = es.load("inequality_decomposition")
    year = es.DISPLAY_YEAR

    print("REGRESSION TEST — recompute with the ETL's own convention (floor_rule=None)")
    print("%-24s %-21s %-21s" % ("series", "within (ours / ETL)", "between (ours / ETL)"))
    worst = 0.0
    for s in sorted(bins.series.unique()):
        got = decompose(bins, s, year, floor_rule=None)
        exp = published[(published.series == s) & (published.year == year)].iloc[0]
        dw = abs(got["within"] - exp.mld_within) / exp.mld_within
        db = abs(got["between"] - exp.mld_between) / exp.mld_between
        worst = max(worst, dw, db)
        print("%-24s %9.6f / %9.6f %9.6f / %9.6f  max rel %.1e"
              % (s, got["within"], exp.mld_within, got["between"], exp.mld_between, max(dw, db)))
    print("\nworst relative disagreement with the ETL: %.2e" % worst)
    assert worst < 1e-6, "recompute does NOT reproduce the ETL — do not proceed"
    print("PASS — the recompute is faithful.\n")

    print("THE DECK'S CONVENTION — WID bottom-coded at 1%% of country mean, PIP untouched")
    print("%-24s %8s %8s %10s %9s" % ("series", "within", "between", "between %", "bins coded"))
    for s in sorted(bins.series.unique()):
        g = decompose(bins, s, year)
        print("%-24s %8.3f %8.3f %9.1f%% %9d%s"
              % (s, g["within"], g["between"], 100 * g["between_share"],
                 g["num_bins_coded"], "" if g["floor_rule"] else "   (PIP convention unchanged)"))


if __name__ == "__main__":
    main()
