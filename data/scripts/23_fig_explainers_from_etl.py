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

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"

# --- the MLD anatomy figure ---
MLD_SOURCES = {
    "WID_pretax_per_adult": "WID — pre-tax national income, per adult",
    "PIP": "PIP — disposable income or consumption, per capita",
}
DECILE_BINS = [f"p{d}p{d + 1}" for d in range(10, 100, 10)]

# --- the top-adjustment figure ---
SPLICE_PERCENTILE = 95
ANCHOR_BIN = "p94p95"
SHAPE_SOURCE = "WID_posttax_per_capita"
BASE_SOURCE = "PIP_consinc"


def sig4(x):
    """Four significant figures, as the original figure scripts wrote them."""
    return float(f"{x:.4g}")


def main():
    year = es.DISPLAY_YEAR
    print(f"Reading the ETL cache (display year {year})")
    bins = es.load("display_year_bins")
    example = es.load("example_country_bins")
    by_country = es.load("inequality_decomposition_by_country")
    model = es.load("consumption_income_model")
    dual = es.load("pip_dual_percentiles")

    write(mld_decomposition_figure(example, by_country, year), "fig_mld_decomp_explainer.json")
    write(top_adjustment_figure(bins, year), "fig_topadj_explainer.json")
    write(consumption_income_figure(dual, model), "fig_consinc_explainer.json")


# ---------------------------------------------------------------------------
# 1. Anatomy of the MLD decomposition
# ---------------------------------------------------------------------------
def mld_decomposition_figure(example, by_country, year):
    """Per-country decile dots, country means and the between/within split, for the
    three example countries — the decomposition restricted to those three.

    Restricting is exact rather than a re-estimate: the ETL publishes each
    country's weight, mean and within-country MLD, and the decomposition is
    additive in those, so the subset only needs the weights renormalising.
    """
    k = es.DAILY_TO_MONTHLY
    ex = example[example["year"] == year]
    bc = by_country[(by_country["year"] == year) & by_country["country"].isin(es.EXAMPLE_COUNTRIES)]

    out_sources = []
    for source, label in MLD_SOURCES.items():
        g = bc[bc["series"] == source]
        assert len(g) == len(es.EXAMPLE_COUNTRIES), f"missing country rows for {source}"
        # Keep the configured order; the ETL table is sorted alphabetically.
        g = g.set_index("country").reindex(es.EXAMPLE_COUNTRIES).reset_index()
        assert g["country"].tolist() == es.EXAMPLE_COUNTRIES
        w = g["population_weight"].to_numpy(float)
        mu_c = g["mean"].to_numpy(float)
        within_c = g["mld_within"].to_numpy(float)
        p = w / w.sum()
        mu = float((p * mu_c).sum())
        between = float((p * np.log(mu / mu_c)).sum())
        within = float((p * within_c).sum())

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
                f"{es.ETL_VERSION}/harmonized_income_distributions. Weights are WID's "
                "demography matched to each series' basis; zero incomes are floored at "
                "$0.01/day inside the MLD only.",
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
def top_adjustment_figure(bins, year):
    """Per country: the observed PIP curve, the income-basis curve where it differs,
    and the top-adjusted values above the splice bin."""
    k = es.DAILY_TO_MONTHLY
    d = bins[bins["year"] == year]

    ref = d[d["series"] == "PIP"].sort_values(["country", "p_low"])
    labels = ref[ref["country"] == ref["country"].iloc[0]]["percentile"].tolist()
    assert len(labels) == 109 and labels[94] == ANCHOR_BIN, "unexpected bin structure"
    anchor_idx = labels.index(ANCHOR_BIN)
    mids = (
        ref[ref["country"] == ref["country"].iloc[0]]
        .assign(mid=lambda t: (t["p_low"] + t["p_high"]) / 2 * 100)["mid"]
        .round(3)
        .tolist()
    )

    def curves(series):
        s = d[d["series"] == series].sort_values(["country", "p_low"])
        countries = s.loc[s["p_low"] == 0, "country"].tolist()
        vals = s["avg"].to_numpy(float).reshape(len(countries), 109)
        return dict(zip(countries, vals))

    pip = curves("PIP")
    consinc = curves("PIP_consinc")
    adj = curves("PIP_topadj")

    data = {}
    n_adjusted = 0
    for c in sorted(pip):
        if c not in consinc or c not in adj:
            continue
        entry = {"pip": [sig4(v * k) for v in pip[c]]}
        # The income-basis line is drawn only where it actually differs from the
        # observed PIP curve, i.e. for the consumption-based countries.
        if not np.allclose(consinc[c], pip[c], rtol=1e-9):
            entry["consinc"] = [sig4(v * k) for v in consinc[c]]
            n_adjusted += 1
        # The adjusted series equals its base up to the anchor by construction;
        # only the grafted tail is carried.
        assert np.allclose(adj[c][: anchor_idx + 1], consinc[c][: anchor_idx + 1], rtol=1e-6), (
            f"adjusted series differs below the anchor for {c}"
        )
        entry["adj"] = [sig4(v * k) for v in adj[c][anchor_idx + 1 :]]
        data[c] = entry

    print(f"  top adjustment: {len(data)} countries ({n_adjusted} consumption-based)")
    default = "Indonesia" if "Indonesia" in data else sorted(data)[0]
    return {
        "meta": {
            "title": "The top adjustment, applied on top of the income-basis adjustment",
            "splice_percentile": SPLICE_PERCENTILE,
            "anchor_bin": ANCHOR_BIN,
            "anchor_index": anchor_idx,
            "shape_source": SHAPE_SOURCE,
            "base_source": BASE_SOURCE,
            "default_country": default,
            "year": year,
            "units": "international-$ per month (converted from daily at 365/12)",
            "notes": [
                "Chain: consumption (observed) -> income basis -> top-adjusted above P95.",
                "adj holds values only for bins above the anchor; below that the "
                "adjusted series equals the income-basis series.",
                "consinc is present only for consumption-based countries; for income "
                "countries the income basis IS the observed PIP series.",
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
def consumption_income_figure(dual, model):
    """Per consumption-based country: the observed consumption curve, the income
    curve the regression predicts from it, and — where PIP publishes one for the
    same year — the actual income curve, as an in-sample check."""
    k = es.DAILY_TO_MONTHLY
    alpha = model.set_index("percentile")["alpha"]
    beta = model.set_index("percentile")["beta"]
    pct = list(range(1, 101))
    a = np.exp(alpha.loc[pct].to_numpy(float))
    b = beta.loc[pct].to_numpy(float)

    countries = {}
    n_dual = 0
    for c, g in dual.groupby("country", observed=True):
        year = int(g["year"].iloc[0])
        cons = g[g["welfare_type"] == "consumption"].sort_values("percentile")["avg"].to_numpy(float)
        if len(cons) != 100 or (cons <= 0).any():
            continue
        # The model is fitted on DAILY values, so it is applied before the
        # per-month conversion.
        pred = a * cons**b
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
            "title": "Consumption → income: the fitted mapping, country by country",
            "default_country": default,
            "units": (
                "international-$ per month, 2021 PPPs (converted from daily at 365/12; "
                "the model itself is fitted on daily values)"
            ),
            "model": (
                "ln y_p = alpha_p + beta_p ln c_p, fitted per percentile on PIP's dual "
                "country-years — see garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions#consumption_income_model"
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
