"""
27_fig_between_share_trend.py — the between/within split, read across time.

The ETL computes the MLD decomposition for every year the two sources share
(1990-2024), on the same common sample, at constant prices, with the same
zero-income floor. This script reshapes that panel into one JSON for the
`fig-between-share-trend` component: one line per series, the between-country
share of global MLD by year, plus the three MLD components for a metric toggle.

    data/figures/fig_between_share_trend.json

Reads the committed ETL cache (see etl_source.py); run refresh_from_etl.py to
update the cache first.

WHAT THE CHART CAN AND CANNOT SAY
---------------------------------
Levels and the long trend are comparable across years: fixed sample, constant
prices, one floor. Year-to-year wiggles are mostly the machinery behind each
source's panel, which the JSON records as notes and the component prints:

  - WID's country-years are WID's own extrapolations for 63-84% of the panel,
    and 97% in 2023-2024 (WID's observed series end earlier);
  - PIP's are survey years for only 13-51% of countries in any given year, the
    rest lined up by the World Bank, and 2023-2024 are nowcasts;
  - two to four countries switch welfare concept (income <-> consumption) in a
    typical year, each with a small step in the PIP income-basis series.

Run:  python data/scripts/27_fig_between_share_trend.py
"""

import json
from pathlib import Path

import etl_source as es

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"

# Years drawn as "mostly extrapolated / nowcast": WID's extrapolated share of
# country-years jumps from ~0.7 to 0.97 in 2023, and PIP's 2023-2024 values are
# nowcasts. Measured on the 2026-08-25 build; the component shades from here.
SHADE_FROM = 2023

# Direct end labels need to be short; the full labels stay in meta.sources.
SHORT_LABELS = {
    "WID_pretax_per_adult": "WID pre-tax, per adult",
    "WID_pretax_per_capita": "WID pre-tax, per capita",
    "WID_posttax_per_adult": "WID post-tax, per adult",
    "WID_posttax_per_capita": "WID post-tax, per capita",
    "WID_posttax_rescaled": "WID post-tax, rescaled",
    "PIP_topadj": "PIP top-adjusted",
    "PIP_consinc": "PIP income basis",
    "PIP": "PIP",
}

METRICS = [
    {
        "key": "between_share",
        "label": "Between-country share of global MLD",
        "unit": "%",
        "note": "Between-country MLD divided by total MLD. The fraction of global inequality that is about which country you live in.",
    },
    {
        "key": "mld_total",
        "label": "Total MLD",
        "unit": "",
        "note": "Mean log deviation of the pooled world distribution over the common sample.",
    },
    {
        "key": "mld_between",
        "label": "Between-country MLD",
        "unit": "",
        "note": "MLD of the world if everyone earned their country's mean.",
    },
    {
        "key": "mld_within",
        "label": "Within-country MLD",
        "unit": "",
        "note": "Population-weighted average of each country's own MLD.",
    },
]


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    dec = es.load("inequality_decomposition")
    years = sorted(int(y) for y in dec["year"].unique())
    n_countries = sorted(int(n) for n in dec["num_countries"].unique())
    assert len(n_countries) == 1, f"The common sample changes across years: {n_countries}"
    n_countries = n_countries[0]
    print(f"  years {years[0]}-{years[-1]} | {n_countries} countries in every year")

    data = {}
    for s in es.BRIDGING_ORDER:
        d = dec[dec["series"] == s].set_index("year").reindex(years)
        assert d["between_share"].notna().all(), f"{s}: missing years"
        data[s] = {m["key"]: [round(float(v), 6) for v in d[m["key"]]] for m in METRICS}

    out = {
        "meta": {
            "title": "Between-country share of global inequality, 1990-2024",
            "years": years,
            "n_countries": n_countries,
            "shade_from": SHADE_FROM,
            "metrics": METRICS,
            "series": [
                {"key": s, "label": es.DECK_SERIES_LABELS[s], "short": SHORT_LABELS[s]} for s in es.BRIDGING_ORDER
            ],
            "sources": {s: es.DECK_SERIES_LABELS[s] for s in es.BRIDGING_ORDER},
            "etl_version": es.ETL_VERSION,
            "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
            "generated_by": "27_fig_between_share_trend.py",
            "notes": [
                f"Same {n_countries} countries in every year, constant prices, the same $0.01/day "
                "floor on zero incomes — so levels and the long trend are comparable across years.",
                "WID country-years are WID's own extrapolations for 63-84% of the panel and 97% in "
                "2023-2024; PIP's are survey years for 13-51% of countries in any year, the rest "
                "lined up by the World Bank, with 2023-2024 nowcasts. Year-to-year wiggles are "
                "mostly this machinery.",
                "Two to four countries switch welfare concept in a typical year, each a small step "
                "in the PIP income-basis series.",
                "Computed by OWID's ETL: garden/poverty_inequality/"
                f"{es.ETL_VERSION}/harmonized_income_distributions.",
            ],
        },
        "data": data,
    }

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / "fig_between_share_trend.json"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"  wrote {path.relative_to(Path(__file__).resolve().parents[2])} ({path.stat().st_size / 1024:.0f} KB)")

    print("\nbetween-country share of global MLD:")
    for s in es.BRIDGING_ORDER:
        v = data[s]["between_share"]
        pick = {y: v[years.index(y)] for y in (1990, 2000, 2010, 2015, 2020, years[-1])}
        print(f"  {s:<24} " + "  ".join(f"{y}: {x:5.1%}" for y, x in pick.items()))


if __name__ == "__main__":
    main()
