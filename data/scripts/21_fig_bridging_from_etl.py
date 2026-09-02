"""
21_fig_bridging_from_etl.py — the Q2 bridging figures, sourced from OWID's ETL.

Replaces 10_fig_raw_comparison.py and 14_fig_bridging_all.py. Those scripts
computed the derived series and the MLD decomposition locally, from the
harmonised file built by stages 02-03; the ETL now does all of that (see
etl_source.py). This script only reshapes ETL output into the two JSONs the
`fig-raw-comparison` component already reads:

    data/figures/fig_raw_comparison.json   3 example countries, lollipops + bars
    data/figures/fig_bridging_all.json     the full common sample, bars only

WHAT IS UNCHANGED
-----------------
The JSON contract, including the deck's own series names (WID_pretax_per_adult,
PIP_topadj, ...). The component and every `sources` prop in content/slides.json
keep working untouched.

WHAT IS NEW
-----------
Both JSONs now carry EVERY YEAR the two sources share (1990-2024), not just
2023, because the ETL computes the whole panel. Each JSON gains:

    meta.years        the available years
    meta.default_year the year shown unless a slide overrides it
    mld_by_year       {year: [ ...the same records as `mld`... ]}
    lollipop_by_year  {year: [ ...the same records as `lollipop`... ]}

`mld` and `lollipop` still hold the default year, so a component that ignores
the new fields behaves exactly as before.

Run:  python data/scripts/21_fig_bridging_from_etl.py
"""

import json
from pathlib import Path

import numpy as np

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
DEFAULT_YEAR = 2023

# Method parameters, recorded in the JSON meta for provenance. These are the
# ETL step's constants, not choices made here.
SPLICE_PERCENTILE = 95
ANCHOR_BIN = "p94p95"
ZERO_REPLACEMENT = 0.01

NOTES_COMMON = [
    "Computed by OWID's ETL: garden/poverty_inequality/"
    f"{es.ETL_VERSION}/harmonized_income_distributions.",
    "MLD weighting convention: ALL series are weighted by one demographic yardstick "
    "independent of both sources — Our World in Data's population series for total "
    "population, UN World Population Prospects for adults aged 20+ — matched to each "
    "series' basis (adults for per-adult, total population otherwise), so the two "
    "sources' population disagreements never enter the comparison. WID's per-adult "
    "series are still converted to per capita with WID's own adult share. (The deck "
    "originally weighted by WID's demography; the switch moved every between share "
    "by at most 0.02pp, since WID's counts are UN WPP too.)",
    f"Zero incomes are replaced with ${ZERO_REPLACEMENT}/day inside the MLD only. "
    "This matters for the WID PRE-TAX series, where the bottom ~5 percentiles of "
    "almost every country are zero (4.3% of the sample population in 2023): "
    "across floors from $0.001 to $1.00/day the pre-tax between-country share "
    "moves by about 5 percentage points. It does not affect the PIP-side series "
    "(no zero bins) and barely affects WID post-tax (0.05% of population).",
]


def global_mld_records(dec, year):
    """The GLOBAL decomposition for one year, over the whole common sample — one
    record per series, in bridging order. Read straight from the ETL table."""
    d = dec[dec["year"] == year].set_index("series")
    out = []
    for s in es.BRIDGING_ORDER:
        if s not in d.index:
            continue
        r = d.loc[s]
        out.append(
            {
                "between": float(r["mld_between"]),
                "within": float(r["mld_within"]),
                "total": float(r["mld_total"]),
                "between_share": float(r["between_share"]),
                "grand_mean": float(r["grand_mean"]),
                "zero_bins_replaced": int(r["num_zero_bins_replaced"]),
                "source": s,
                "label": es.DECK_SERIES_LABELS[s],
            }
        )
    return out


def subset_mld_records(by_country, year, countries):
    """The decomposition restricted to `countries` — the pedagogical "if the world
    were just these three" version the per-country slide shows.

    This is EXACT, not a re-estimate. The MLD decomposition is additive in
    population-weighted country terms, and the ETL publishes each country's
    weight, mean and within-country MLD, so restricting the sample is just a
    matter of renormalising the weights:

        P_c     = w_c / sum(w over the subset)
        mu      = sum(P_c * mu_c)
        between = sum(P_c * ln(mu / mu_c))
        within  = sum(P_c * mld_within_c)

    The country means and within-MLDs already carry the ETL's zero-income floor,
    so the subset inherits the same conventions as the global figure.
    """
    d = by_country[(by_country["year"] == year) & (by_country["country"].isin(countries))]
    out = []
    for s in es.BRIDGING_ORDER:
        g = d[d["series"] == s]
        if g.empty:
            continue
        w = g["population_weight"].to_numpy(float)
        mu_c = g["mean"].to_numpy(float)
        within_c = g["mld_within"].to_numpy(float)
        p = w / w.sum()
        mu = float((p * mu_c).sum())
        between = float((p * np.log(mu / mu_c)).sum())
        within = float((p * within_c).sum())
        out.append(
            {
                "between": between,
                "within": within,
                "total": between + within,
                "between_share": between / (between + within),
                "grand_mean": mu,
                "source": s,
                "label": es.DECK_SERIES_LABELS[s],
                "countries": [
                    {
                        "country": c.country,
                        "pop": float(c.population_weight),
                        "mean": float(c.mean),
                        "mld_within": float(c.mld_within),
                    }
                    for c in g.itertuples()
                ],
            }
        )
    return out


def lollipop_records(bins, year):
    """The `lollipop` array for one year: P10 / P90 / mean / extremes, per month."""
    k = es.DAILY_TO_MONTHLY
    d = bins[bins["year"] == year]
    out = []
    for s in es.BRIDGING_ORDER:
        for c in es.EXAMPLE_COUNTRIES:
            g = d[(d["series"] == s) & (d["country"] == c)]
            if g.empty:
                continue
            by_pct = g.set_index("percentile")["avg"]
            out.append(
                {
                    "source": s,
                    "country": c,
                    "p10": float(by_pct["p10p11"]) * k,
                    "p90": float(by_pct["p90p91"]) * k,
                    "mean": float(np.average(g["avg"], weights=g["pop"])) * k,
                    "p0": float(by_pct["p0p1"]) * k,
                    "p999": float(by_pct["p99.9p100"]) * k,
                }
            )
    return out


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    dec = es.load("inequality_decomposition")
    by_country = es.load("inequality_decomposition_by_country")
    bins = es.load("example_country_bins")

    years = sorted(int(y) for y in dec["year"].unique())
    default_year = DEFAULT_YEAR if DEFAULT_YEAR in years else years[-1]
    n_countries = int(dec.loc[dec["year"] == default_year, "num_countries"].iloc[0])
    print(f"  years {years[0]}-{years[-1]} | {n_countries} countries in the common sample")

    sources = {s: es.DECK_SERIES_LABELS[s] for s in es.BRIDGING_ORDER}
    meta_common = {
        "sources": sources,
        "years": years,
        "default_year": default_year,
        "etl_version": es.ETL_VERSION,
        "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        "zero_replacement_usd_per_day": ZERO_REPLACEMENT,
        "topadj_splice_percentile": SPLICE_PERCENTILE,
        "topadj_anchor_bin": ANCHOR_BIN,
        "topadj_shape_source": "WID_posttax_per_capita",
        "topadj_base_source": "PIP_consinc",
        "rescale_mean_source": "PIP_topadj",
        # Bare filename: the component prints this after "Pipeline: ", and the
        # source note is close to the frame width already.
        "generated_by": "21_fig_bridging_from_etl.py",
    }

    # ---- Figure 1: three example countries, lollipops + bars ----------------
    out1 = {
        "meta": {
            **meta_common,
            "title": "Raw comparison: WID vs PIP, three countries",
            "countries": es.EXAMPLE_COUNTRIES,
            "units": (
                "international-$ PER MONTH (PIP: 2021 PPPs; WID: latest PPP vintage); "
                "converted from daily values at 365/12"
            ),
            "notes": [
                "P10/P90 are the bin averages of p10p11 / p90p91.",
                "The MLD bars here are computed over these three countries ONLY — "
                "a pedagogical mini-world, not the global decomposition (that is the "
                "all-countries figure). Restricting the sample is exact: the ETL "
                "publishes each country's weight, mean and within-country MLD, and the "
                "decomposition is additive in those.",
                *NOTES_COMMON,
            ],
        },
        "lollipop": lollipop_records(bins, default_year),
        "mld": subset_mld_records(by_country, default_year, es.EXAMPLE_COUNTRIES),
        "lollipop_by_year": {str(y): lollipop_records(bins, y) for y in years},
        "mld_by_year": {
            str(y): subset_mld_records(by_country, y, es.EXAMPLE_COUNTRIES) for y in years
        },
    }
    write(out1, "fig_raw_comparison.json")

    # ---- Figure 2: full sample, bars only (empty lollipop) -----------------
    def bars_only(year):
        return global_mld_records(dec, year)

    out2 = {
        "meta": {
            **meta_common,
            "title": "The bridging steps, across the whole common sample",
            "row2_title": (
                f"Global inequality across all {n_countries} countries&rsquo; "
                "populations combined — MLD level, decomposed"
            ),
            "scope_note": f"all {n_countries} countries covered by both PIP and WID",
            "n_countries": n_countries,
            "units": (
                "MLD is unit-free; underlying incomes in international-$ "
                "(PIP: 2021 PPPs; WID: latest PPP vintage)"
            ),
            "notes": [
                "lollipop is deliberately EMPTY: that switches the component into "
                "bars-only mode (no per-country lollipop row).",
                *NOTES_COMMON,
            ],
        },
        "lollipop": [],
        "mld": bars_only(default_year),
        "mld_by_year": {str(y): bars_only(y) for y in years},
    }
    write(out2, "fig_bridging_all.json")

    # A quick look at the default year, so a run reports its own numbers.
    print(f"\n{default_year} between-country share of global MLD:")
    for rec in out2["mld"]:
        print(f"  {rec['source']:<24} {rec['between_share']:6.1%}  (total MLD {rec['total']:.3f})")


def write(obj, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    path.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"  wrote {path.relative_to(Path(__file__).resolve().parents[2])} "
          f"({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
