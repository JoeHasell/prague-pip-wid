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

ONE YEAR, NOT THIRTY-FIVE (2026-09-08)
--------------------------------------
These JSONs used to carry every year 1990-2024 in `mld_by_year` /
`lollipop_by_year`, on the theory that a component might expose a year control.
None ever did — `fig-raw-comparison` reads the flat `mld` / `lollipop` arrays
and hardcodes 2023 in its source note — so the blocks were ~35x of dead weight
in four figure files. They are gone. The only genuine MLD time series in the
deck is `fig_between_share_trend` (one slide), which has its own script.

The decompositions here are now COMPUTED from the ETL's bins rather than read
from its ready-made `inequality_decomposition` tables, because the deck applies
its own zero-income floor to the WID series — see etl_mld.py for why, and
`etl_mld.main()` for the regression test proving the recompute reproduces the
ETL exactly when the ETL's own convention is used.

THE `variants` BLOCK (2026-09-09)
---------------------------------
Both global-bar figures also carry a `variants` block: the 2x3 cross of top
adjustment method (graft / share match) x anchor (P95 / P98 / P99), keyed a-f,
for the only two series that move with that choice — PIP_topadj, and
WID_posttax_rescaled, whose country means are forced onto it. Each entry has
that variant's decomposition, plus a `range` of the min and max of each field
taken SEPARATELY, so a range's endpoints need not come from one variant. The
`fig-raw-comparison` component draws it under `variants: true` (one thin bar per
variant, inside the same column footprint) and says so on the chart.

Run:  python data/scripts/21_fig_bridging_from_etl.py
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import consinc
import etl_mld
import etl_source as es
import rescale
import topadj

FIGURES_DIR = Path(__file__).resolve().parents[1] / "figures"
DEFAULT_YEAR = 2023

# Method parameters, recorded in the JSON meta for provenance. The splice is the
# deck-wide baseline — read it, never restate it, or a figure silently drifts
# from the series it plots.
TOPADJ_METHOD = es.TOPADJ_METHOD
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
    "Zero incomes: the WID series are BOTTOM-CODED at 1% of each country's own "
    "raw mean before the MLD is taken; PIP is left as the World Bank publishes it "
    "(already bottom-coded at $0.28/day, and it has no zero bins). WID's pre-tax "
    "series reports exactly zero for the bottom ~5 percentiles of almost every "
    "country — DINA allocates zero rather than dropping people — and at the ETL's "
    "$0.01/day floor those bins supplied a median 43.5% of each country's "
    "within-MLD, putting an artificial floor of about 0.7 under it. See "
    "data/README.md and etl_mld.py.",
]


def mld_records(bins, year, with_countries=False):
    """The decomposition for one year over EVERY country in `bins` — one record
    per series, in bridging order.

    Computed here from the bins rather than read from the ETL's ready-made
    decomposition, because the deck applies its own zero-income floor (see
    etl_mld.py). Called with the whole common sample this is the global
    decomposition; called with the three example countries' bins it is the
    pedagogical "if the world were just these three" version, which is exact
    because the decomposition is additive in population-weighted country terms.
    """
    out = []
    for s_ in es.BRIDGING_ORDER:
        if s_ not in set(bins["series"].unique()):
            continue
        # expect_bins=None: PIP_topadj is ragged when the top-1% method
        # re-ranks (etl_source.TOPADJ_METHOD), and every other series is checked
        # on the grid by load_bins itself.
        g = etl_mld.decompose(bins, s_, year, expect_bins=None)
        out.append(
            {
                "between": g["between"],
                "within": g["within"],
                "total": g["total"],
                "between_share": g["between_share"],
                "grand_mean": g["grand_mean"],
                "zero_bins_replaced": g["num_zero_bins"],
                "bins_bottom_coded": g["num_bins_coded"],
                "source": s_,
                "label": es.DECK_SERIES_LABELS[s_],
                # Per-country detail only for the small pedagogical sample; on the
                # global figure it would be 211 x 8 records the component never reads.
                **({"countries": [
                    {"country": c, "pop": float(r.population_weight),
                     "mean": float(r["mean"]), "mld_within": float(r.mld_within)}
                    for c, r in g["by_country"].iterrows()]} if with_countries else {}),
            }
        )
    return out


# TWO INDEPENDENT SETS OF VARIANTS, one per modelling choice, each attached to
# the columns that actually move with it, and each keyed with its own alphabet
# so the two can never be confused one slide apart.
#
# 1. The top adjustment: two methods x four bases = eight scenarios. Both act on
#    the TOP 1% ONLY (no anchor choice any more) and differ in what they assume
#    the survey got wrong — under-reporting (match) or under-representation
#    (append); see topadj.build_top1. The four bases are raw PIP and the
#    income-basis series at each of WID's three slopes, so the grid prices the
#    two modelling choices against each other. Moves PIP_topadj and
#    WID_posttax_rescaled (whose country means are forced onto it).
# REPORTED METHODS. Both are built and both work (topadj.build_top1); only
# `append` is SHOWN. Joe dropped `match` from the deck on 2026-09-09 — it lands
# close enough to append that carrying both only complicated the story. Put
# "match" back in this tuple to restore it everywhere it used to appear.
TOPADJ_METHODS = ("append",)
# The key alphabet is SHARED with the consumption->income set below: i/ii/iii
# name the same three slopes in both columns, so one key line serves both. "NA"
# is the top-1% adjustment applied to raw PIP, with no cons->income step at all
# — a different kind of thing, so it is drawn set apart and left out of the
# labelled range.
TOPADJ_KEYS = ("NA", "i", "ii", "iii")
TOPADJ_ASIDE = ("NA",)
TOPADJ_BASES = [("PIP", None)] + [(None, b) for b in consinc.WID_PROFILE_B_SCENARIOS]
TOPADJ_SPEC = [(m, base, beta) for m in TOPADJ_METHODS for base, beta in TOPADJ_BASES]
TOPADJ_VARIED = ("PIP_topadj", "WID_posttax_rescaled")
SLOPE_CAPTION = "Consumption\u2192income slope (and the base for the top-1% adjustment)"

# 2. The consumption -> income slope: WID's three values for b. Moves
#    PIP_consinc, and everything downstream of it — but the downstream columns
#    are left single valued here, because a slide that split both at once would
#    be showing the cross, not this one choice.
# Roman numerals, not a/b/c: the top-adjustment set uses the letters, and the
# two sets sit on consecutive build-up slides, so distinct keys stop "b" from
# meaning two different things one slide apart. (A tuple, not a string —
# "iii" is not one character.)
CONSINC_KEYS = ("i", "ii", "iii")
CONSINC_VARIED = ("PIP_consinc",)
CONSINC_CAPTION = SLOPE_CAPTION


def _envelopes(out, caption):
    """{series: [records]} -> {series: {variants, range, caption}}.

    The ranges are taken component by component and share by share, so an
    endpoint pair need not come from a single variant — `within` bottoms out at
    the P99 graft while `between` tops out at the P95 graft. That is deliberate
    and stated on the slide: the range answers "how far can this component move",
    not "which single bar is the extreme".
    """
    res = {}
    for s, recs in out.items():
        # An `aside` variant is drawn but deliberately left OUT of the labelled
        # range: it answers a different question from the others, so pooling it
        # into one min-max would misdescribe the spread.
        inrange = [r for r in recs if not r.get("aside")]
        rng = {}
        for f in ("within", "between", "total", "between_share"):
            v = [r[f] for r in inrange]
            rng[f] = [min(v), max(v)]
        res[s] = {"variants": recs, "range": rng, "caption": caption}
    return res


def consinc_variant_records(bins, year, welfare):
    """PIP_consinc under each of WID's three slopes, at the baseline top adjustment."""
    import consinc
    keep = ~bins["series"].isin(("PIP_consinc",) + TOPADJ_VARIED)
    out = {s: [] for s in CONSINC_VARIED}
    for key, b in zip(CONSINC_KEYS, consinc.WID_PROFILE_B_SCENARIOS):
        ci = consinc.build_pip_consinc_profile(bins[keep], welfare, b=b,
                                               out_series="PIP_consinc")
        full = pd.concat([bins[keep], ci], ignore_index=True)
        for s in CONSINC_VARIED:
            g = etl_mld.decompose(full, s, year)
            out[s].append({"key": key, "beta": b,
                           # Just the value: the caption names the parameter, and a
                           # label of "b = 0.10" would read as "b b = 0.10" against
                           # the variant key letters a/b/c in the chart's key line.
                           "label": f"\u03b2 {b:.2f}",
                           "is_baseline": b == consinc.WID_PROFILE_B,
                           "within": round(g["within"], 4),
                           "between": round(g["between"], 4),
                           "total": round(g["total"], 4),
                           "between_share": round(g["between_share"], 5)})
    return _envelopes(out, CONSINC_CAPTION)


def variant_records(bins, year, welfare):
    """PIP_topadj and WID_posttax_rescaled under each of the eight scenarios.

    Each cell is rebuilt END TO END from its own base: raw PIP or the income
    basis at that slope, then the top-1% method on top of it, then WID post-tax
    rescaled onto the result. The append scenarios land off the 109-bin grid
    (see topadj.build_top1), so their decomposition skips the grid guard.
    """
    keep = ~bins["series"].isin(("PIP_consinc",) + TOPADJ_VARIED)
    upstream = bins[keep]
    out = {s_: [] for s_ in TOPADJ_VARIED}
    for key, (method, base, beta) in zip(TOPADJ_KEYS, TOPADJ_SPEC):
        if base == "PIP":
            frame = upstream.copy()
            base_series, label_base = "PIP", "no cons\u2192income step"
        else:
            ci = consinc.build_pip_consinc_profile(upstream, welfare, b=beta,
                                                   out_series="PIP_consinc")
            frame = pd.concat([upstream, ci], ignore_index=True)
            base_series, label_base = "PIP_consinc", f"\u03b2 {beta:.2f}"
        ta = topadj.build_top1(frame, method, base_series=base_series,
                               out_series="PIP_topadj")
        base_frame = pd.concat([frame, ta], ignore_index=True)
        rs = rescale.build_from_bins(base_frame, mean_source="PIP_topadj")
        full = pd.concat([base_frame, rs], ignore_index=True)
        for s_ in TOPADJ_VARIED:
            g = etl_mld.decompose(full, s_, year, expect_bins=None)
            out[s_].append({"key": key, "method": method, "base": label_base,
                            "label": label_base,
                            "aside": key in TOPADJ_ASIDE,
                            "within": round(g["within"], 4),
                            "between": round(g["between"], 4),
                            "total": round(g["total"], 4),
                            "between_share": round(g["between_share"], 5)})
    return _envelopes(out, SLOPE_CAPTION)


def rank_window(g, lo, hi):
    """Population-weighted average income over the rank window [lo, hi].

    SELECT BY RANK, NEVER BY BIN LABEL. A label lookup ("p90p91") assumes the
    frame is on the deck's grid and that its ranks mean what the label says —
    which stops being true the moment a series is re-ranked (the append top-1%
    method re-reads every rank as 0.99 x its old value) or lands on a different
    grid. Integrating the window works on any frame: 100 bins, the ETL's 109,
    a ragged one, or a re-ranked one.

    Each bin is treated as uniform across its own width, which is all the bin
    data supports.
    """
    p0 = g["p_low"].to_numpy(dtype=float)
    p1 = g["p_high"].to_numpy(dtype=float)
    w = np.clip(np.minimum(p1, hi) - np.maximum(p0, lo), 0, None)
    assert w.sum() > 0, f"empty rank window [{lo}, {hi}]"
    return float(np.average(g["avg"].to_numpy(dtype=float), weights=w))


def lollipop_records(bins, year):
    """The `lollipop` array for one year: P10 / P90 / mean / extremes, per month.

    P10 and P90 are the average income of the population between those ranks and
    the next percentile — read off as rank windows, not bin labels.
    """
    k = es.DAILY_TO_MONTHLY
    d = bins[bins["year"] == year]
    out = []
    for s in es.BRIDGING_ORDER:
        for c in es.EXAMPLE_COUNTRIES:
            g = d[(d["series"] == s) & (d["country"] == c)].sort_values("p_low")
            if g.empty:
                continue
            out.append(
                {
                    "source": s,
                    "country": c,
                    "p10": rank_window(g, 0.10, 0.11) * k,
                    "p90": rank_window(g, 0.90, 0.91) * k,
                    "mean": float(np.average(g["avg"], weights=g["pop"])) * k,
                    "p0": rank_window(g, 0.00, 0.01) * k,
                    # the top 1% since the deck moved to a percentile grid; it was
                    # the top 0.1% while the ETL's ten sub-bins were carried
                    "p999": rank_window(g, es.TOP1_START, 1.00) * k,
                }
            )
    return out


def main():
    print(f"Reading ETL version {es.ETL_VERSION} from the committed cache")
    # display_year_bins is the whole common sample for the display year;
    # example_country_bins is the three-country mini-world.
    global_bins = es.load_bins("display_year_bins")
    bins = es.load_bins("example_country_bins")

    default_year = DEFAULT_YEAR
    years = [default_year]
    n_countries = int(global_bins.loc[global_bins["year"] == default_year, "country"].nunique())
    print(f"  {default_year} | {n_countries} countries in the common sample")
    # The two variant sets are merged into ONE dict keyed by series, so a slide
    # picks what to split with the component's `variants` prop (true = all with a
    # block; an array = only those). No series appears in both sets.
    basis = es.load("pip_welfare_basis")
    basis = basis[basis["year"] == default_year]
    welfare = dict(zip(basis["country"], basis["welfare_type"]))
    variants = variant_records(global_bins, default_year, welfare)
    variants.update(consinc_variant_records(global_bins, default_year, welfare))
    assert set(variants) == set(TOPADJ_VARIED) | set(CONSINC_VARIED), \
        "a variant set has collided with another"
    for sname, v in variants.items():
        r = v["range"]
        print("  %-24s between share %.1f-%.1f%% | within %.3f-%.3f | total %.3f-%.3f"
              % (sname, 100 * r["between_share"][0], 100 * r["between_share"][1],
                 r["within"][0], r["within"][1], r["total"][0], r["total"][1]))
    print(f"  zero-income floor: WID bottom-coded at "
          f"{etl_mld.DECK_FLOOR_RULE[1]:.0%} of each country's raw mean; PIP unchanged")

    sources = {s: es.DECK_SERIES_LABELS[s] for s in es.BRIDGING_ORDER}
    meta_common = {
        "sources": sources,
        "years": years,
        "default_year": default_year,
        "etl_version": es.ETL_VERSION,
        "etl_dataset": f"garden/poverty_inequality/{es.ETL_VERSION}/harmonized_income_distributions",
        "wid_floor_rule": "1% of each country's raw mean",
        "pip_floor_rule": "unchanged (World Bank bottom-coding, $0.28/day)",
        "topadj_method": TOPADJ_METHOD,
        
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
                "international-$/month (daily x365/12); 2021 PPPs; PIP at 2021 prices, WID at 2025 prices"
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
        "mld": mld_records(bins, default_year, with_countries=True),
    }
    write(out1, "fig_raw_comparison.json")

    # ---- Figure 2: full sample, bars only (empty lollipop) -----------------
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
                "MLD is unit-free; underlying incomes in international-$; 2021 PPPs; PIP at 2021 prices, WID at 2025 prices"
            ),
            "notes": [
                "lollipop is deliberately EMPTY: that switches the component into "
                "bars-only mode (no per-country lollipop row).",
                *NOTES_COMMON,
            ],
        },
        "lollipop": [],
        "mld": mld_records(global_bins, default_year),
        "variants": variants,
    }
    write(out2, "fig_bridging_all.json")

    # ---- Figure 3: example countries above, GLOBAL bars below --------------
    # The pairing the rebuilt bridge sequence is built on: the lollipop row
    # illustrates what a distribution looks like in three countries, while the
    # bars below report the decomposition over the WHOLE common sample. The two
    # rows therefore have DIFFERENT scopes on purpose, which the row title and
    # the source note both spell out.
    out3 = {
        "meta": {
            **meta_common,
            "title": "Three example countries, global decomposition",
            "countries": es.EXAMPLE_COUNTRIES,
            "row2_title": (
                f"Global inequality across all {n_countries} countries&rsquo; "
                "populations combined &mdash; MLD level, decomposed"
            ),
            "scope_note": (
                f"all {n_countries} countries covered by both PIP and WID "
                "&mdash; not the three shown above, which are examples"
            ),
            "n_countries": n_countries,
            "units": (
                "international-$/month (daily x365/12); 2021 PPPs; PIP at 2021 prices, WID at 2025 prices"
            ),
            "notes": [
                "P10/P90 are the bin averages of p10p11 / p90p91.",
                "MIXED SCOPE, deliberately: the lollipops above are three example "
                f"countries; the bars below are the GLOBAL decomposition over all "
                f"{n_countries} countries, NOT those three. Contrast "
                "fig_raw_comparison.json, where both rows are the same three countries.",
                *NOTES_COMMON,
            ],
        },
        "lollipop": lollipop_records(bins, default_year),
        "mld": mld_records(global_bins, default_year),
        "variants": variants,
    }
    write(out3, "fig_examples_global_mld.json")

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
