"""
mld.py — THE definition of MLD decomposition for this project.

Every MLD (mean log deviation) calculation in this project goes through this
module, because it bakes in two project-wide conventions:

1. POPULATION WEIGHTS COME FROM WID, MATCHED TO THE SERIES' BASIS
   (decided 2026-08-11). WID and PIP disagree about population levels (e.g.
   the US: 343.5M in WID vs 336.8M in PIP). If each series were weighted by
   its own source's populations, that demographic disagreement would leak
   into the between-country component. So ALL weights come from WID's
   demography — but matched to what the series measures, so every column is
   an internally coherent object:
       per-capita series (incl. PIP and derived series):
           weight = WID_total_population(country) * bin_width
       per-adult series (source name contains "per_adult"):
           weight = WID_adult_population(country) * bin_width
   Consequences:
     - Within-country MLD is unaffected by the yardstick (within a country
       all bins share the same total, which cancels).
     - PIP is weighted by WID demography too: the sources' population
       disagreement never enters any comparison.
     - Any two PER-CAPITA series with identical country means have IDENTICAL
       between components (e.g. the mean-rescaled WID series matches the
       series it takes its means from — PIP_topadj in the deck).
     - The per-adult -> per-capita bridging step changes weights along with
       incomes: that is the point — the adult/total distinction IS the step.
   The basis is inferred from the source name ("per_adult" -> adults); pass
   basis="adult"/"total" explicitly for series whose name doesn't say.
   `mld_decomposition(..., weights="pip")` computes the decomposition under
   PIP's (total) populations instead — sensitivity reporting only, and only
   for per-capita series (PIP has no adult counts).

2. ZERO INCOMES are replaced by $0.01/day INSIDE the MLD calculation only
   (log of zero is undefined). The replacement value is a parameter; the old
   project's sensitivity analysis put the impact of this choice at ~3pp on
   the between share at global scale.
"""

import numpy as np

# Harmonized sources whose `pop` columns carry WID total / adult populations.
WID_TOTAL_POP_SOURCE = "WID_pretax_per_capita"
WID_ADULT_POP_SOURCE = "WID_pretax_per_adult"


def country_floor(x, w, rule):
    """THE definition of a bottom-coding floor for one country's bins.

    `rule` is a (kind, value) pair:
        ("absolute", v)       floor at v, in the data's own units ($/day here).
                              PIP's own published convention is ("absolute", 0.28).
        ("mean_fraction", f)  floor at f x the country's RAW mean — LIS practice
                              (historically f = 0.01). Scale-invariant, so it is
                              unaffected by the price base or per-adult/per-capita
                              basis.
        None                  no floor.

    The mean used to set a "mean_fraction" floor is the RAW mean, computed before
    any coding, so the floor cannot depend on itself. Callers apply the returned
    value with np.maximum(x, floor) and then compute the index on the CODED
    distribution — i.e. the MLD's mu is the coded mean. That is what LIS does and
    what makes the result the MLD of an actual distribution rather than a hybrid.

    Returns None when no floor applies.
    """
    if rule is None:
        return None
    kind, value = rule
    if kind == "absolute":
        return float(value)
    if kind == "mean_fraction":
        return float(value) * float(np.average(np.asarray(x, dtype=float),
                                               weights=np.asarray(w, dtype=float)))
    raise ValueError(f"unknown floor rule kind: {kind!r}")


def reference_populations(h, weights="wid", basis="total"):
    """Country -> population under the chosen yardstick and basis (persons).

    weights="wid" (THE project convention) or "pip" (sensitivity only).
    basis="total" or "adult" (WID only; PIP has no adult counts).
    """
    if weights == "pip":
        assert basis == "total", "PIP has no adult populations"
        src = "PIP"
    else:
        src = WID_ADULT_POP_SOURCE if basis == "adult" else WID_TOTAL_POP_SOURCE
    d = h[h.source == src]
    return d.groupby("country")["pop"].sum()


def mld_decomposition(h, source, countries, zero_replacement=0.01,
                      weights="wid", basis=None, floor_rule=None):
    """Between/within MLD decomposition of `source` over `countries`.

    Weights follow the project convention: WID demography, matched to the
    series' basis (see module docstring). basis=None infers from the source
    name ("per_adult" -> adults, else total); pass explicitly otherwise.
    weights="pip" is for sensitivity reporting only.

    Zero handling: by default zeros are replaced by `zero_replacement` and
    nothing else is touched (the historical convention). Pass `floor_rule` to
    bottom-code instead — see country_floor() for the rules.

    Returns a dict: between, within, total, between_share, grand_mean,
    zero_bins_replaced, bins_bottom_coded, and per-country details.
    """
    if basis is None:
        basis = "adult" if "per_adult" in source else "total"
    ref_pop = reference_populations(h, weights, basis)
    missing = [c for c in countries if c not in ref_pop.index]
    assert not missing, f"no {weights.upper()} population for: {missing}"

    d = h[(h.source == source) & (h.country.isin(countries))].sort_values(
        ["country", "p_low"])
    n_bins = d.groupby("country").size()
    assert (n_bins == 109).all(), \
        f"missing bins for {source}: {n_bins[n_bins != 109].to_dict()}"

    x = d["average"].to_numpy(dtype=float)
    country = d["country"].to_numpy()
    # The convention: reference country population spread over bins by width
    w = (d["country"].map(ref_pop) * (d["p_high"] - d["p_low"])).to_numpy(dtype=float)

    # Zero handling. The default reproduces the historical convention exactly:
    # replace zeros with `zero_replacement`, touch nothing else. `floor_rule`
    # instead bottom-codes every bin, per country, via country_floor() above.
    n_replaced = int((x == 0).sum())
    if floor_rule is None:
        x = np.where(x == 0, zero_replacement, x)
        n_bottom_coded = n_replaced
    else:
        n_bottom_coded = 0
        for c in countries:
            m = country == c
            f = country_floor(x[m], w[m], floor_rule)
            n_bottom_coded += int((x[m] < f).sum())
            x[m] = np.maximum(x[m], f)

    total_pop = w.sum()
    mu = np.average(x, weights=w)

    within_total = 0.0
    between_total = 0.0
    details = []
    for c in countries:
        m = country == c
        pop_c = w[m].sum()
        mu_c = np.average(x[m], weights=w[m])
        mld_c = np.average(np.log(mu_c / x[m]), weights=w[m])
        within_total += (pop_c / total_pop) * mld_c
        between_total += (pop_c / total_pop) * np.log(mu / mu_c)
        details.append({"country": c, "pop": pop_c, "mean": mu_c,
                        "mld_within": mld_c})

    total = float(np.average(np.log(mu / x), weights=w))
    # Exact decomposition identity — if this trips, the code is wrong.
    assert abs(total - (within_total + between_total)) < 1e-9, \
        f"decomposition identity violated for {source}"

    return {
        "between": float(between_total),
        "within": float(within_total),
        "total": total,
        "between_share": float(between_total / total),
        "grand_mean": float(mu),
        "zero_bins_replaced": n_replaced,
        "bins_bottom_coded": n_bottom_coded,
        "floor_rule": floor_rule,
        "countries": details,
    }
