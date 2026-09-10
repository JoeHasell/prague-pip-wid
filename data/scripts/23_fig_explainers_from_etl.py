"""
23_fig_explainers_from_etl.py — the three Q2 explainer figures, from OWID's ETL.

Replaces 11_fig_topadj_explainer.py, 12_fig_mld_decomp_explainer.py and
13_fig_consinc_explainer.py. Those computed the derived series and the
decomposition locally; the ETL now does all of it (see etl_source.py). This
script only reshapes ETL output into the three JSONs the components already read:

    data/figures/fig_mld_decomp_explainer.json   <- fig-mld-decomp
    data/figures/fig_topadj_explainer.json       <- fig-topadj-explainer
    data/figures/fig_consinc_explainer.json      <- fig-consinc-explainer

The JSON contracts are unchanged, so no component or slide needs editing.

Run:  python data/scripts/23_fig_explainers_from_etl.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import consinc
import etl_mld
import topadj

METHODS = ("match", "append")
import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"

# --- the MLD anatomy figure ---
MLD_SOURCES = {
    "WID_pretax_per_adult": "WID — pre-tax national income, per adult",
    "PIP": "PIP — disposable income or consumption, per capita",
}
DECILE_BINS = [f"p{d}p{d + 1}" for d in range(10, 100, 10)]

# --- the top-adjustment figure ---
TOPADJ_METHOD = es.TOPADJ_METHOD                 # the deck-wide baseline method
BETAS = consinc.WID_PROFILE_B_SCENARIOS          # WID's three cons->inc slopes
BASE_BETA = consinc.WID_PROFILE_B                # the deck-wide baseline
TOP1_START = topadj.TOP1_START
SHAPE_SOURCE = "WID_posttax_per_capita"
BASE_SOURCE = "PIP_consinc"


def sig4(x):
    """Four significant figures, as the original figure scripts wrote them."""
    return float(f"{x:.4g}")


def main():
    year = es.DISPLAY_YEAR
    print(f"Reading the ETL cache (display year {year})")
    bins = es.load_bins("display_year_bins")
    example = es.load_bins("example_country_bins")
    by_country = es.load("inequality_decomposition_by_country")
    model = es.load("consumption_income_model")
    dual = es.load("pip_dual_percentiles")
    basis = es.load("pip_welfare_basis")
    basis = basis[basis["year"] == year]
    welfare = dict(zip(basis["country"], basis["welfare_type"]))

    write(mld_decomposition_figure(example, by_country, year), "fig_mld_decomp_explainer.json")
    write(top_adjustment_figure(bins, year, welfare), "fig_topadj_explainer.json")
    write(consumption_income_figure(dual), "fig_consinc_explainer.json")


# ---------------------------------------------------------------------------
# 1. Anatomy of the MLD decomposition
# ---------------------------------------------------------------------------
def mld_decomposition_figure(example, by_country, year):
    """Per-country decile dots, country means and the between/within split, for the
    three example countries — the decomposition restricted to those three.

    Computed from the three countries' bins under the deck's zero-income floor
    (etl_mld), not read from the ETL's ready-made table, so this explainer shows
    the same arithmetic as the bridging figure it explains. Restricting to three
    countries is exact rather than a re-estimate: the decomposition is additive
    in population-weighted country terms, so the subset only needs the weights
    renormalising.
    """
    k = es.DAILY_TO_MONTHLY
    ex = example[example["year"] == year]

    out_sources = []
    for source, label in MLD_SOURCES.items():
        d = etl_mld.decompose(example, source, year)
        g = d["by_country"].reindex(es.EXAMPLE_COUNTRIES)
        assert not g.isna().any().any(), f"missing country rows for {source}"
        g = g.reset_index().rename(columns={"index": "country"})
        w = g["population_weight"].to_numpy(float)
        mu_c = g["mean"].to_numpy(float)
        within_c = g["mld_within"].to_numpy(float)
        p = w / w.sum()
        mu, between, within = d["grand_mean"], d["between"], d["within"]

        countries = []
        for i, row in enumerate(g.itertuples()):
            d = ex[(ex["series"] == source) & (ex["country"] == row.country)]
            deciles = d.set_index("percentile")["avg"]
            countries.append(
                {
                    "country": row.country,
                    "mean": round(float(row.mean) * k, 4),
                    "within_mld": round(float(row.mld_within), 4),
                    "pop_share": round(float(p[i]), 4),
                    "pop": round(float(row.population_weight)),
                    "deciles": {b: round(float(deciles[b]) * k, 4) for b in DECILE_BINS},
                }
            )

        out_sources.append(
            {
                "source": source,
                "label": label,
                # what the weights count, per the basis-matched convention
                "weight_basis": "adults" if "per_adult" in source else "people",
                "mu": round(mu * k, 4),
                "between": round(between, 4),
                "within": round(within, 4),
                "total": round(between + within, 4),
                "between_share": round(between / (between + within), 4),
                "countries": countries,
            }
        )
        print(f"  {source}: mu={mu:.1f} between={between:.3f} within={within:.3f}")

    return {
        "meta": {
            "title": "Anatomy of the MLD decomposition",
            "countries": es.EXAMPLE_COUNTRIES,
            "decile_bins": DECILE_BINS,
            "year": year,
            "units": (
                "international-$ per month (converted from daily at 365/12; MLD terms "
                "are unit-free and unconverted)"
            ),
            "notes": [
                "Dots are decile bin averages (p10p11 ... p90p91).",
                "Identity: ln(mu/x) = ln(mu/mu_c) + ln(mu_c/x); MLD is the "
                "population-weighted average of these gaps.",
                "Computed by OWID's ETL: garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions. Weights are one "
                "demographic yardstick for every series — OWID population for totals, UN WPP "
                "adults 20+ for per-adult series — matched to each series' basis; zero "
                "incomes are floored at $0.01/day inside the MLD only.",
                "The three-country decomposition is derived from the published "
                "per-country weights, means and within-country MLDs, which the "
                "decomposition is additive in — so restricting the sample is exact.",
            ],
            "generated_by": "23_fig_explainers_from_etl.py",
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        },
        "sources": out_sources,
    }


# ---------------------------------------------------------------------------
# 2. How the top-adjusted series is built
# ---------------------------------------------------------------------------
def top_adjustment_figure(bins, year, welfare):
    """Per country: the observed PIP curve, the income-basis curve at each of
    WID's three slopes, and the top-1% adjustment by each method.

    CROSSED OVER BOTH MODELLING CHOICES: `consinc[beta]` and
    `variants[beta][method]`, so the chart can hold one choice and vary the
    other. Beta keys are the slope to 2dp.

    HOW THE TWO METHODS ARE STORED. Both act on the top 1% only, so almost
    nothing needs carrying:

      match   the top 1% keeps its ranks and takes one new value — a single
              number, applied to all ten of the base's 0.1% bins.
      append  the whole survey is re-read as the bottom 99%, so every rank is
              multiplied by 0.99 (which the chart can do itself, no data needed),
              the survey's own top 1% collapses to one bin at [0.9801, 0.99],
              and a new bin is appended at [0.99, 1]. Two numbers.

      adjusted  false where the gate fired (WID's top share is not above the
                base's, so the country is left alone) — both methods then equal
                the income basis.
    """
    k = es.DAILY_TO_MONTHLY
    d = bins[bins["year"] == year]

    ref = d[d["series"] == "PIP"].sort_values(["country", "p_low"])
    first = ref[ref["country"] == ref["country"].iloc[0]]
    labels = first["percentile"].tolist()
    assert len(labels) == es.DECK_BINS, "not on the deck's percentile grid"
    mids = ((first["p_low"] + first["p_high"]) / 2 * 100).round(3).tolist()
    top_idx = [i for i, lo in enumerate(first["p_low"]) if lo >= TOP1_START - 1e-9]
    assert top_idx == [es.DECK_BINS - 1], top_idx

    def curves_from(frame):
        f = frame.sort_values(["country", "p_low"])
        countries = f.loc[f["p_low"] == 0, "country"].tolist()
        n = len(f) // len(countries)
        assert len(f) == n * len(countries), "ragged bins"
        return dict(zip(countries, f["avg"].to_numpy(float).reshape(len(countries), n)))

    pip = curves_from(d[d["series"] == "PIP"])
    upstream = d[~d["series"].isin(["PIP_consinc", "PIP_topadj", "WID_posttax_rescaled"])]

    ci_by_beta, adj_by_beta, gates = {}, {}, {}
    for b in BETAS:
        bk = f"{b:.2f}"
        ci = consinc.build_pip_consinc_profile(upstream, welfare, b=b,
                                               out_series="PIP_consinc")
        frame = pd.concat([upstream, ci], ignore_index=True)
        ci_by_beta[bk] = curves_from(ci)
        gates[bk] = topadj.top1_shares(frame, "PIP_consinc")
        adj_by_beta[bk] = {
            "match": curves_from(topadj.build_top1(frame, "match", out_series="V",
                                                   grid=True)),
            "append": {c: g.sort_values("p_low")["avg"].to_numpy(float)
                       for c, g in topadj.build_top1(frame, "append", out_series="V")
                       .groupby("country", observed=True)},
        }
    base_bk = f"{BASE_BETA:.2f}"
    deck_ci = curves_from(d[d["series"] == "PIP_consinc"])
    for c in deck_ci:
        assert np.allclose(ci_by_beta[base_bk][c], deck_ci[c], rtol=1e-9), \
            f"rebuilt income basis at b={base_bk} differs from the deck's for {c}"

    data = {}
    n_adjusted = 0
    for c in sorted(pip):
        entry = {"pip": [sig4(v * k) for v in pip[c]]}
        if not np.allclose(ci_by_beta[base_bk][c], pip[c], rtol=1e-9):
            entry["consinc"] = {f"{b:.2f}": [sig4(v * k) for v in ci_by_beta[f"{b:.2f}"][c]]
                                for b in BETAS}
            n_adjusted += 1
        entry["variants"] = {}
        for b in BETAS:
            bk = f"{b:.2f}"
            on = bool(gates[bk].loc[c, "adjust"])
            m = adj_by_beta[bk]["match"][c]
            a = adj_by_beta[bk]["append"][c]
            entry["variants"][bk] = {
                "adjusted": on,
                "match": sig4(float(m[99]) * k),
                # the appended frame is one bin longer than the grid when
                # adjusted (the retained survey plus WID's appended percentile)
                # and exactly the grid when the gate fired
                "append": {"top_pip": sig4(float(a[-2]) * k) if on else None,
                           "top_wid": sig4(float(a[-1]) * k) if on else None},
            }
        data[c] = entry

    print(f"  top adjustment: {len(data)} countries ({n_adjusted} consumption-based), "
          f"{len(BETAS)} slopes x {len(METHODS)} methods")
    default = "Indonesia" if "Indonesia" in data else sorted(data)[0]
    return {
        "meta": {
            "title": "The top-1% adjustment, applied on top of the income-basis adjustment",
            "method": TOPADJ_METHOD,
            "top1_start": TOP1_START,
            "methods": [{"key": "match", "label": "Match WID's top-1% share"},
                        {"key": "append", "label": "Append WID's top 1%"}],
            "betas": [f"{b:.2f}" for b in BETAS],
            "base_beta": base_bk,
            "profile_a": consinc.WID_PROFILE_A,
            "shape_source": SHAPE_SOURCE,
            "base_source": BASE_SOURCE,
            "default_country": default,
            "year": year,
            "units": "international-$ per month (converted from daily at 365/12)",
            "notes": [
                "Chain: consumption (observed) -> income basis -> top-1% adjusted.",
                "Crossed over both modelling choices: consinc[beta] and "
                "variants[beta][method]; base_beta and method name the deck's baseline.",
                "match keeps the top 1% where it is and changes its level; append "
                "re-reads the whole survey as the bottom 99% (so every rank scales "
                "by 0.99) and adds a new top percentile.",
                "adjusted=false means the gate fired: WID's top-1% share is not above "
                "the base's, so the country is left alone.",
                "consinc is present only for consumption-based countries; for income "
                "countries the income basis IS the observed PIP series at every slope.",
                "Computed by OWID's ETL: garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions.",
            ],
            "generated_by": "23_fig_explainers_from_etl.py",
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        },
        "percentiles": {"labels": labels, "mids": mids},
        "countries": data,
    }


# ---------------------------------------------------------------------------
# 3. The consumption -> income mapping, country by country
# ---------------------------------------------------------------------------
def consumption_income_figure(dual, model=None):
    """Per consumption-based country: the observed consumption curve, the income
    curve the correction profile predicts from it, and — where PIP publishes one
    for the same year — the actual income curve, as an out-of-sample check.

    Since 2026-09-09 the mapping is WID's scaled-logit profile with WID's own
    parameters (consinc.py), not a regression fitted on these countries. So the
    actual-income comparison is now genuinely OUT of sample: nothing here was
    used to estimate the profile, which makes it a real test rather than a
    goodness-of-fit display.
    """
    k = es.DAILY_TO_MONTHLY
    pct = np.arange(1, 101)
    mid = (pct - 0.5) / 100.0                      # each percentile's midpoint rank
    profile = consinc.correction_profile(mid)

    countries = {}
    n_dual = 0
    for c, g in dual.groupby("country", observed=True):
        year = int(g["year"].iloc[0])
        cons = g[g["welfare_type"] == "consumption"].sort_values("percentile")["avg"].to_numpy(float)
        if len(cons) != 100 or (cons <= 0).any():
            continue
        # A pure per-rank rescaling, so the order of this and the per-month
        # conversion does not matter.
        pred = profile * cons
        entry = {"year": year, "cons": [sig4(v * k) for v in cons], "pred": [sig4(v * k) for v in pred]}
        inc = g[g["welfare_type"] == "income"].sort_values("percentile")["avg"].to_numpy(float)
        if len(inc) == 100:
            entry["inc"] = [sig4(v * k) for v in inc]
            n_dual += 1
        countries[c] = entry

    print(f"  consumption->income: {len(countries)} countries ({n_dual} with an actual income series)")
    default = "Albania" if "Albania" in countries else sorted(countries)[0]
    return {
        "meta": {
            "title": "Consumption → income: the correction profile, country by country",
            "default_country": default,
            "units": "international-$ per month, 2021 PPPs (converted from daily at 365/12)",
            "model": (
                f"Q_I(p) / Q_C(p) = {consinc.WID_PROFILE_A} + {consinc.WID_PROFILE_B} "
                "log(p/(1-p)) — WID's scaled-logit correction profile with WID's "
                "parameters (Chancel, Cogneau, Gethin & Myczkowski 2019, WID.world "
                "Working Paper 2019/13, Table A.1). Not fitted on PIP; see consinc.py "
                "for why PIP's dual country-years are not a usable estimation sample."
            ),
            "notes": [
                "Each country shown at its most recent national year with a consumption "
                "series, preferring a year that also has an income series.",
                "For dual countries the actual income series is included — an "
                "in-sample fit check.",
                "The estimation sample contains no Sub-Saharan Africa or South Asia, so "
                "applying the mapping there is an out-of-sample transfer.",
            ],
            "generated_by": "23_fig_explainers_from_etl.py",
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        },
        "countries": countries,
    }


def write(obj, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    path.write_text(json.dumps(obj, separators=(",", ":")))
    print(f"  wrote {name} ({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
