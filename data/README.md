# Data pipeline

> **NEW (2026-08): the figures are now sourced from OWID's ETL.**
>
> The methodology below — harmonising PIP and WID onto one 109-bin structure, the
> three bridging series, the between/within MLD decomposition — has been ported
> into OWID's ETL as two versioned garden datasets. The deck no longer computes
> any of it locally. What this buys:
>
> - **It updates itself.** Every PIP and WID release re-runs the whole thing.
>   (The local pipeline's PIP extract is pinned to catalog version `2025-10-13`;
>   the World Bank has since revised it, moving 15 countries' 2023 means by more
>   than 5% — Bosnia −30%, Turkey +20%, Germany −9%. The global bars shift by
>   ≤0.1pp, but individual countries do move.)
> - **No Stata, no 1–2 hour WID fetch.** The ETL already holds WID's percentile
>   distributions for every year, PPP-converted.
> - **Every year, not just 2023.** The ETL runs 1990–2024, so the figure JSONs now
>   carry the whole panel (`meta.years`, `mld_by_year`, `lollipop_by_year`).
> - **One implementation.** The method exists once, with sanity checks that gate
>   the build, instead of twice in two places that can drift.
>
> ### ⚠️ The figures do NOT update themselves — you must run the refresh
>
> The ETL re-runs on every PIP and WID release, but **this repo does not notice.**
> The figures the deck renders are JSON files committed here, built from a cached
> extract in `data/raw/etl/`. Until someone runs the refresh, the slides keep
> showing whatever was cached last. **Run this after any ETL change, and before
> presenting:**
>
> ```bash
> # Reads the public OWID catalog (owid/etl#6764 merged on 2026-09-02); no VPN needed:
> python data/scripts/refresh_from_etl.py
>
> # While an ETL pull request that changes these datasets is still open — and this is
> # where the committed figures come from today (owid/etl#6806, WID 2026-09-02):
> python data/scripts/refresh_from_etl.py --staging worktree-etl-data-wid-update
>
> # From a local owid/etl checkout in which the branch has been built (etlr) — what an
> # ETL developer uses, and the fallback once a staging server has been torn down:
> python data/scripts/refresh_from_etl.py --local /path/to/owid/etl
>
> # Change nothing, just report whether the committed figures are stale:
> python data/scripts/refresh_from_etl.py --check
> ```
>
> **All four ETL datasets the figures read follow the same three tiers** (public
> catalog → an ETL branch's staging server → the committed cache): the two harmonized
> datasets, plus `inequality_comparison` and the WID dataset itself. So a figure
> refresh never has to wait for an ETL pull request to merge — point it at the branch.
> PIP's percentiles and inequality, the thousand-bins regions and OWID's regions are
> long published and always come from the catalog.
>
> **Until owid/etl#6806 merges, the catalog modes stop with an error** naming the
> missing path: `etl_source.WID_VERSION` is `2026-09-02`, which the catalog does not
> carry yet. That is deliberate — the alternative is a raw pyarrow error, or silently
> refreshing from a version that no longer exists. Use `--staging` until then; after
> the merge, `refresh_from_etl.py` with no arguments is the normal route again.
>
> Then **commit `data/raw/etl/`, `data/figures/`,
> `data/processed/reference_year_indicators.csv` and `data/processed/global_gini_averages.csv` together**. `--check` rebuilds into a
> temporary directory, restores the committed figures and dataset whatever happens, and
> exits non-zero when they no longer match the ETL — so it is safe to run any time and
> works as a pre-talk sanity check.
>
> It runs the cache refresh, every figure script in dependency order, and then the two
> ETL-derived dataset scripts (`33_reference_year_indicators.py` and `36_global_gini_averages.py`,
> see "Reference-year indicators" below). Running them by hand still works if you need one in isolation:
>
> ```bash
> python data/scripts/20_cache_from_etl.py            # the ETL cache
> python data/scripts/21_fig_bridging_from_etl.py     # Q2 figures
> python data/scripts/22_fig_reference_year_trends.py # Q1 reference-year panel
> python data/scripts/23_fig_explainers_from_etl.py   # the Q2 explainers
> python data/scripts/24_fig_top_of_distribution_from_etl.py  # Q3
> python data/scripts/25_fig_scatters_from_etl.py     # Q1 scatters
> python data/scripts/26_fig_reference_year_observed.py  # Q1, observed only
> python data/scripts/27_fig_between_share_trend.py    # Q2 between-share over time
> python data/scripts/28_fig_means_from_etl.py         # surveys vs national accounts
> python data/scripts/29_fig_mld_scatter.py            # within-MLD, PIP vs WID
> python data/scripts/31_fig_top1_share_scatter.py     # top-1% shares, PIP chain vs WID
> python data/scripts/33_reference_year_indicators.py  # the reference-year DATASET (not a figure)
> python data/scripts/34_fig_refyear_scatter.py        # year-vs-year scatters with selectable years, from 33_
> python data/scripts/36_global_gini_averages.py       # average country Gini by year, a DATASET + its figure, from 33_
> ```
>
> One script is deliberately NOT part of the refresh: `python data/scripts/35_fit_consinc_wb.py`
> re-fits the Wollburg et al. consumption→income model on PIP's dual surveys (network: the OWID
> catalog) and writes `data/processed/consinc_wb_fit.json`, which is committed; `consinc.py`
> hardcodes the resulting constants and `python data/scripts/consinc.py` checks them against
> that file. Re-run it only when PIP's percentiles table changes.
>
> **Reference-year indicators** (`data/processed/reference_year_indicators.csv`) is the
> ETL's `inequality_comparison` idea applied to the deck's ADJUSTED PIP: for every
> reference year 1990–2024, each country's nearest PIP survey year within ±5 (ties to the
> earlier survey; no excluded years), with Gini, top-10% and top-1% shares, Palma and
> the mean computed from the bins for PIP, PIP_consinc and PIP_topadj (and the parallel
> Wollburg chain) —
> and the two WID per-capita series at the reference year itself, from the same code on
> the same 100-bin grid. It lives in `data/processed/` but is built from the ETL cache
> (`reference_year_bins`, `wid_reference_year_indicators`, `pip_welfare_basis`), not by
> the local pipeline. Each reference year is matched on its own; use `refyears.pair()` to
> compare two of them under the ETL's same-welfare rule. Provenance and caveats are in
> the script's docstring; the matcher and the indicator code are `data/scripts/refyears.py`.
>
> **Global Gini averages** (`data/processed/global_gini_averages.csv`, `36_global_gini_averages.py`)
> averages that dataset's country Ginis for every reference year and series, unweighted and
> weighted by population at the reference year (one yardstick for every series: the WID
> per-capita bins' population), over four country samples: the countries PIP matches that year
> (WID restricted to them), a balanced panel of the 77 countries PIP matches every year, each
> source's own coverage, and the common sample without China and India. It is an average of
> within-country inequality, not the Gini of the world distribution. The same script writes
> `data/figures/fig_global_gini_average.json` for `components/fig-global-gini-average.js`
> (appendix slides `slide-global-gini-panels`, `-unweighted`, `-weighted`, `-ex-china-india`; the
> first and last use the component's `layout: "panels"`, PIP and WID side by side with an
> unweighted and a weighted line in each).
>
> **One trap the refresh cannot catch for you.** `etl_source.ETL_VERSION` pins the
> dataset version (currently `2026-08-25`). New data flowing through the *same*
> version folder is picked up automatically, but when the ETL mints a *new* version
> folder — which it does whenever a derived step is repointed at newer dependencies
> — that constant must be bumped first, or the refresh will faithfully rebuild the
> old version and report no drift. This is the same trap `config.PIP_URL` set for
> the old pipeline.
>
> **The original scripts (00–04, `mld.py`, `topadj.py`, `rescale.py`,
> `consinc.py`, `scenarios.py`, `10_`/`14_fig_*`) are left untouched** and still
> work off the committed raw caches. They are the reference implementation the
> ETL port was verified against, and are safe to delete once you are happy with
> the ETL-sourced figures. **Since 2026-09-02 the eight that write figure JSONs
> (`10`–`17`) refuse to run without `--write-legacy-figures`** — they share
> filenames with the ETL scripts, so running one silently replaced whole-panel
> ETL output with 2023-only local output. See `legacy_guard.py`. Everything they documented about method choices still
> applies — the ETL preserves each one, including the MLD weighting convention
> and the zero-income floor.
>
> One thing worth knowing about that floor: it is doing real work on the WID
> **pre-tax** series, where the bottom ~5 percentiles are exactly zero in 185 of
> 211 countries (4.3% of the sample population). Moving it from $0.001 to
> $1.00/day moves the pre-tax between-country share by about 5 percentage points
> (20.1% → 25.6%), and dropping zero bins instead gives 28.0%. It does not touch
> the PIP-side series (no zero bins) and barely touches WID post-tax (0.05% of
> population). The PIP-vs-WID contrast the deck draws survives every one of those
> choices — the gap stays above 41 points — but the WID pre-tax *level* should be
> read as a band, not a point.


This folder contains the full, reproducible pipeline behind the data-driven
figures in this deck. It produces **one dataset that everything downstream
should build on**:

```
data/processed/pip_wid_harmonized_2023.csv
```

— full income distributions (109 quantile bins per country) for ~211–218
countries in 2023, from the two main global sources, on an identical bin
structure so that any statistic can be computed the same way for both:

| `source` value | concept | population basis | countries |
|---|---|---|---|
| `PIP` | disposable income / consumption (survey) | per capita | 218 |
| `WID_pretax_per_adult` | pre-tax national income (`ptinc`) | per adult | 211 |
| `WID_pretax_per_capita` | pre-tax national income | per capita | 211 |
| `WID_posttax_per_adult` | post-tax **national** income (`diinc`) | per adult | 211 |
| `WID_posttax_per_capita` | post-tax national income | per capita | 211 |

Columns: `source, country, year, percentile, p_low, p_high, pop, average, share`.
`average` is mean **daily** income in the bin, in PPP international dollars.
Both sources use the **2021 PPP round**; they differ in *price base* — PIP at
2021 prices, WID at 2025 prices. See [Prices, PPPs and the two price
bases](#prices-ppps-and-the-two-price-bases). `pop` is the number of people
(or adults, for per-adult series) in the bin. `share` is the bin's share of
the country's total income.

## Prices, PPPs and the two price bases

Every monetary value in this project is in **PPP international dollars**, but
the two sources are not on the same footing, and the difference is easy to
state wrongly. Two things vary independently:

| | what it is | PIP | WID |
|---|---|---|---|
| **PPP round** | the set of cross-country relative prices (an ICP round) | 2021 | **2021** |
| **Price base** | the year whose prices the real values are expressed in | 2021 | **2025** |

**The PPP round is the same.** This was checked, not assumed: WID's `xlcusp`
conversion factors, re-expressed at a 2021 price base, reproduce the World
Bank's published 2021 PPP conversion factors for GDP (`PA.NUS.PPP`) for **184
of 197 countries to within 0.01%**, and 191 within 1%. The six countries
outside 1% are currency-unit artefacts, not method: Bulgaria differs by exactly
1.9559 (the BGN/EUR peg — WID has moved to the euro, the World Bank has not),
Zimbabwe by a redenomination factor, and the rest are Pacific micro-states.

So earlier versions of these notes were wrong to say the two sources come from
"different PPP rounds". They do not. **Only the price base differs.**

### Why WID arrives at 2025 prices

WID publishes incomes in constant local currency of the **latest year in the
database**, not of the data year — currently 2025. `xlcusp(Y)` converts local
currency *already at year-Y prices* into international dollars at year-Y
prices, so the conversion must use the factor for the price-base year. Using
`xlcusp(2023)` against 2025-price incomes was a real bug, found in review on
2026-08-27; see `config.PPP_YEAR`.

Both routes into this repo land in the same place:

- **the ETL path** (what the committed figures use): OWID's ETL extracts WID in
  LCU at 2025 prices and converts with `xlcusp(2025)`, so everything in
  `data/raw/etl/` and every `data/figures/fig_*.json` is in
  **2021-PPP international dollars at 2025 prices**;
- **the local pipeline** (the reference implementation): `02_process_wid.py`
  does the same conversion with `config.PPP_YEAR = 2025`.

Verified against each other: US national income per capita, 2023 — ETL cache
71,410.28/yr vs 71,410.40/yr computed from WID's own LCU series. PIP is
untouched by any of this and is already at 2021 prices.

### Considered and not adopted: putting WID on 2021 prices

Investigated 2026-09-08 and **decided against — the deck stays on 2025-price
WID.** Recorded here so it is not re-derived from scratch, and so nobody
mistakes it for a plan.

Putting WID on PIP's basis needs only **one scalar: x0.854244**, the US
national income price index for 2021 (WID's `inyixx999i`, normalised to 1.0 in
2025). One number, every country, every year.

That is not a shortcut past the obvious three-step route (undo `xlcusp(2025)`,
deflate each country's LCU with its *own* inflation, re-convert with
`xlcusp(2021)`). It is that route reduced. `xlcusp` is itself a rebasing of one
underlying PPP by *relative* inflation:

```
xlcusp_c(2021) = xlcusp_c(2025) x inyixx_c(2021) / inyixx_US(2021)
```

so in

```
Y(2021 int-$) = LCU(2025 prices) x inyixx_c(2021) / xlcusp_c(2021)
```

the country's own index appears in the numerator and inside the denominator and
**cancels — it is not skipped, it is already inside `xlcusp(2021)`** — leaving
`Y(2025 int-$) x inyixx_US(2021)`. Which is the general fact that international
dollars are US-price-denominated, so re-basing one is only US deflation.
Verified end to end against directly-fetched WID data: the two routes agree to
9x10^-6 % across 215 countries.

Two things that were established along the way and are worth keeping:

- **the domestic step would have to use WID's own `inyixx999i`**, never an
  externally-sourced deflator. The cancellation is with WID's index;
  substituting the World Bank's GDP deflator breaks it and injects country-level
  errors up to ~20% exactly where the two disagree (Lebanon, Guinea, Comoros,
  Egypt, India);
- **`inyixx999i` is mostly the World Bank GDP deflator** — closer than CPI for
  143 of 168 countries, median error 0.28% vs 2.95%, with CPI or spliced series
  elsewhere. There is no WID-specific "national income deflator"; earlier notes
  here implied one, and that was wrong.

Had it been applied, nothing relative would have moved (a uniform rescale leaves
every MLD, Gini and top share alone, and leaves `PIP_topadj` and
`WID_posttax_rescaled` untouched); WID dollar labels would have fallen 14.6%;
and the one substantive change would have been the means scatter, where the
median WID/PIP ratio goes 2.53x -> 2.16x and the survey share of national income
39.5% -> 46.3% (2023). The proper home for such a fix is OWID's ETL, not a
scalar in this repo — see `etl_source.py`, "WHY THIS EXISTS".

### A difference that a common price base would not fix anyway

Worth knowing when reading any cross-source level comparison: the two
sources deflate *within* a country with different indices: PIP brings a 2023 survey to 2021 prices with national
**CPI**, while WID's constant-price series uses the **GDP deflator**. Both are
honestly on their stated bases; the wedge is small in most countries and large
in high-inflation ones. A common price base would not remove it, so the sources
should not be described as fully comparable in levels.

## Pipeline

```
00_fetch_wid.py  (STATA, ~1-2h) ──> raw/wid/WID_percentiles.csv        ─┐
                                    raw/wid/WID_ppp.csv                 ├─> 02_process_wid.py ──> processed/wid_percentiles_2023.csv ─┐
                                    raw/wid/WID_aggregate_population.csv┘                                                             ├─> 03_harmonize.py ──> processed/pip_wid_harmonized_2023.csv
01_fetch_pip.py  (Python, ~30s) ──> raw/pip/pip_thousand_bins_2023.csv.gz ────────────────────────────────────────────────────────────┘

99_verify.py  — run after any pipeline run; 19 checks, exits non-zero on failure
```

To rebuild everything downstream of the raw WID data (no Stata needed):

```bash
pip install pandas pyarrow
python data/scripts/01_fetch_pip.py     # re-downloads the PIP extract (network)
python data/scripts/02_process_wid.py   # runs off committed raw files
python data/scripts/03_harmonize.py
python data/scripts/99_verify.py
python data/scripts/04_fit_consinc.py  # consumption->income model (network: OWID catalog)
```

Each script's docstring documents exactly what it does and why — read those
before changing anything.

## Figure scripts (10+): one script per deck figure

> ### ⚠️ This section describes the SUPERSEDED local pipeline
>
> Scripts `10`–`17` no longer feed the deck. Every figure they list is now built
> from the ETL by `21`–`24` and `28`, and they write **the same filenames** — so
> running one replaces whole-panel ETL output (1990–2024, current vintage) with
> 2023-only local output. Measured 2026-09-02: the WID between-country share
> moves 3–4pp (WID pre-tax per adult 29.4% → 26.2%) and the per-year data is
> lost. The slides keep rendering normally, so nothing tells you.
>
> They therefore **refuse to run** unless you pass `--write-legacy-figures`
> (`legacy_guard.py`). To rebuild the figures, use
> `python data/scripts/refresh_from_etl.py`.
>
> The section below is kept because it documents the METHOD — the bridging
> series, the MLD convention, the zero handling, the display unit — all of which
> the ETL preserves. Read it for the why; don't run it for the figures.

Scripts numbered `10_fig_*.py` and up each produce the data behind ONE deck
figure, written as a small JSON to `data/figures/`. The matching chart
component in `components/` fetches that JSON at runtime — **no numbers are
hard-coded in component JS**. So the provenance chain for any figure is:

```
slide → component (components/fig-*.js) → data/figures/fig_*.json → data/scripts/10+_fig_*.py → processed/ → raw/
```

**Updated 2026-09-02, in the ETL:** the yardstick is now independent of both
sources — Our World in Data's population series for total population and UN
World Population Prospects for adults aged 20+, still matched to the series'
basis and still applied to every series including PIP. WID's per-adult series
are still converted to per capita with WID's own adult share. Measured effect:
every between share moved by at most 0.02pp, because WID's counts are UN WPP
too (Togo, revised by UN in 2026, and France, which WID counts with its overseas
departments, are the only material differences). The paragraph below records
the original convention the deck's local pipeline used.

**MLD weighting convention (project-wide, decided 2026-08-11):** every MLD
decomposition — for every series, including PIP — weights countries by
**WID's demography, matched to the series' basis**: adult populations for
per-adult series, total populations for per-capita series (`data/scripts/
mld.py`, the single module all MLD calculations go through). Rationale: WID
and PIP disagree about population levels (e.g. the US: 343.5M vs 336.8M),
and per-series weights would leak that demographic disagreement into the
between-country component — while weighting a per-adult income distribution
by whole-population counts would be an incoherent object. Within-country MLD
is unaffected by the yardstick. `mld_decomposition(..., weights="pip")`
exists for sensitivity reporting only (the yardstick choice moves the
3-country PIP between-share by ~0.1pp).

Derived-series methods shared by several figures live in their own modules
(`topadj.py` — the top-adjusted PIP series, in two methods (graft / share
match), with the deck's baseline ANCHOR held in one place,
`etl_source.TOPADJ_SPLICE_PERCENTILE` — see caveat 6; `rescale.py` — WID post-tax
rescaled to the ADJUSTED PIP country means (`mean_source="PIP_topadj"`, so
the WID-side and PIP-side ladders meet at identical country means — and
therefore identical between components); `consinc.py` — PIP adjusted to an income
basis via WID's scaled-logit correction profile, see caveat 5) so
each definition exists once.
Method choices that affect a figure's numbers (e.g. zero-income handling for
MLD) are made and documented in the figure script, and echoed in the JSON's
`meta.notes`.

**To regenerate the deck's figures, run `python data/scripts/refresh_from_etl.py`.**
(This used to read "re-run steps 02–03 and then the figure scripts" — that
instruction predates the ETL port and would now overwrite ETL-sourced figures
with 2023-only local output. Steps 02–03 still rebuild `processed/` for the
reference implementation and for `99_verify.py`; they no longer feed any
figure.)

| script | figure | slide component |
|---|---|---|
| `10_fig_raw_comparison.py` | Raw WID-vs-PIP comparison, 3 countries: P10/P90/mean lollipops + between/within MLD stacked bars | `fig-raw-comparison` |
| `11_fig_topadj_explainer.py` | Interactive explainer of the top-adjusted PIP series (per-country quantile curves, dropdown) | `fig-topadj-explainer` |
| `12_fig_mld_decomp_explainer.py` | Pedagogical anatomy of the MLD decomposition (log-distance gaps, 3 countries, WID pre-tax vs PIP) | `fig-mld-decomp` |
| `13_fig_consinc_explainer.py` | Consumption→income mapping per country: observed consumption, predicted income, actual income for dual countries | `fig-consinc-explainer` |
| `14_fig_bridging_all.py` | The bridging-steps MLD bars over the FULL common sample (all 211 PIP∩WID countries; empty `lollipop` puts the shared component in bars-only mode) | `fig-raw-comparison` |
| `15_fig_top_thresholds.py` | Entry income for the global top 10% / 1% / 0.1% across the seven scenarios (basis-matched populations; marginal-bin threshold) | `fig-top-thresholds` |
| `16_fig_top1_treemap.py` | Country-quantile composition of the global top 1%, per scenario (treemap; box area = population inside the top 1%; regions from `raw/regions/`) | `fig-top1-treemap` |

The seven displayed scenarios (and the shared "build the derived series"
chain) are defined once in `scenarios.py`; the two Q3 scripts import from it.

**Display unit (decided 2026-08-11): the deck shows incomes PER MONTH.** The
pipeline's internal unit remains international-$ **per day** end to end (the
sources arrive daily; the consinc regression is fitted on daily values and
its alpha is unit-specific; the MLD is scale-invariant either way). The
×365/12 conversion (`config.DAILY_TO_MONTHLY`) is applied only inside the
figure scripts, at the point where values are written to `data/figures/`.
`raw/regions/country_region_mapping.csv` is the modified World Bank region
scheme carried over from the old project (Western Europe split out of Europe
& Central Asia; Afghanistan and Pakistan grouped with MENA).

## The raw WID data (and how to refresh it)

`raw/wid/` is a **committed cache** of a WID API pull (last full refresh:
2026-08-11). Refreshing it requires **Stata** with the `wid`
package (`ssc install wid`) and takes ~1–2 hours:

```bash
python data/scripts/00_fetch_wid.py            # full pull (asks first)
python data/scripts/00_fetch_wid.py --resume   # continue after interruption
python data/scripts/00_fetch_wid.py --country US   # single-country test
```

The fetch is country-by-country with progress tracking, because the WID API
is unreliable for large requests. Per-country temp files and progress state
live in `raw/wid/temp_country_data/` and `raw/wid/fetch_progress.json`
(gitignored). After a refresh, re-run steps 02–03 and `99_verify.py`.

## Known caveats (read before interpreting results)

1. **Income concepts differ by construction.** PIP measures disposable
   income *or* consumption, per capita. WID's pre-tax national income is a
   much broader concept (includes undistributed corporate profits, imputed
   returns, etc.). WID's "post-tax" series here is post-tax **national**
   income (DINA `diinc`): all taxes *and all government spending* are
   redistributed back, so each country's post-tax mean equals its pre-tax
   mean (verified in `99_verify.py`). It is **not** disposable income.
   *(An earlier version of this project's documentation mislabeled `diinc`
   as "post-tax disposable income" — corrected here.)*
2. **Per adult vs per capita.** WID's native basis is "equal-split adults";
   PIP's is per capita. The per-capita conversion
   (`avg × adult_pop / total_pop`) assumes the adult share is constant across
   the income distribution within each country.
3. **Price bases differ; PPP rounds do not.** Both sources use the 2021 PPP
   round, but PIP is at 2021 prices and WID at 2025 prices, so WID levels are
   ~17% higher than a like-for-like comparison would put them. Level
   comparisons between sources inherit this; relative measures do not. See
   [Prices, PPPs and the two price bases](#prices-ppps-and-the-two-price-bases).
4. **Zero incomes — and the bottom-coding rule.** WID reports bins of exactly
   zero income (2026-08 pull: 921 pre-tax, 187 post-tax). These are not missing
   data: DINA deliberately allocates zero rather than dropping people, so
   WID's pre-tax series shows exactly zero for the bottom ~5 percentiles in
   **184 of 211 countries**. Zeros are retained in the harmonized file; how to
   treat them is an analysis-stage decision.

   **Since 2026-09-08 this project bottom-codes the WID series at 1% of each
   country's own raw mean** (LIS practice), and leaves PIP exactly as the World
   Bank publishes it — PIP has no zero bins because it is already bottom-coded
   at $0.28/day upstream. The rule lives in one place, `mld.py`'s
   `country_floor()`; `etl_mld.py` applies it on the ETL path and carries a
   regression test showing the recompute reproduces the ETL's published numbers
   to 6e-08 when the ETL's own convention is used.

   **Why the change.** Earlier versions of this note said the choice shifts the
   between-country share by "~3pp". That badly understated it. Under the old
   convention (replace zeros with $0.01/day) those bins supplied a **median
   43.5%** of each country's WID within-MLD — over half for 61 countries. Two
   visible symptoms: an artificial floor of about 0.7 under every country's WID
   within-MLD, and the United States, one of only 26 countries with no zero bins
   and therefore the only ones measured on their own merits, ranking **37th of
   44** on within-MLD against **12th** on WID's own published Gini.

   The 2023 sensitivity, WID pre-tax per capita:

   | convention | within | between share | US rank of 44 |
   |---|---|---|---|
   | $0.01/day, zeros only *(old)* | 1.000 | 28.0% | 37th |
   | $0.28/day, bottom-coded (PIP's floor) | 0.814 | 32.3% | 15th |
   | **1% of country mean, bottom-coded** *(now)* | **0.801** | **32.7%** | **13th** |
   | drop zero bins entirely | 0.713 | 35.3% | 12th |
   | *WID published Gini, for reference* | | | *12th* |

   The chosen rule keeps everyone in the distribution, is scale-invariant (so
   unaffected by the price base or the per-adult/per-capita basis), and
   correlates 0.94 with WID's own Gini against 0.81 under the old convention.
   It leaves PIP untouched and moves WID post-tax by ~0.2pp; the change is
   almost entirely in the WID PRE-TAX series.

   **One exception.** `fig_between_share_trend` (one slide) still uses the old
   convention, because it needs all 35 years of bins and only the display year
   is cached — the deck's WID vintage came from owid/etl#6806's staging server
   and is not in the public catalog. The slide says so.

5. **Consumption -> income uses WID's profile, not a fit on PIP.** PIP mixes
   income and consumption countries; the consumption ones are put on an income
   basis by scaling each rank by a correction profile,

   `Q_I(p) / Q_C(p) = 0.85 + 0.12 * log(p/(1-p))`

   — WID's scaled logit (Chancel, Cogneau, Gethin & Myczkowski 2019, WID.world
   WP 2019/13, section 3.2 and Table A.1), with WID's own parameters. Income is
   below consumption for the poor and above it for the rich, crossing over at
   about P79.

   **The slope is a range, not a point.** WID publish three values for b —
   **0.10 / 0.12 / 0.14** — and b carries the whole shape of the correction
   (a factors out as a level: `a*(1 + (b/a)*logit p)`). At P90 the income/
   consumption ratio is 1.07 / 1.11 / 1.16 across the three; at the top 0.05%
   it is 1.61 / 1.76 / 1.91. All three live in
   `consinc.WID_PROFILE_B_SCENARIOS`, with the middle one — `WID_PROFILE_B`, the
   deck's baseline — asserted to be one of them. Because the top adjustment is
   built ON the income-basis series, the two choices compound rather than add;
   `32_fig_consinc_topadj_cross.py` computes the full 3 x 6 cross (see caveat 6)
   and the deck shows it as a table. Global effect, holding the top adjustment
   at the deck's baseline: between share 57.6% / 55.5% / 53.3%, so the slope is
   worth about 2pp per step — smaller than the top-adjustment choice, which
   moves it about 6pp at a fixed slope.

   **Why not fit it on PIP's own data.** PIP publishes both welfare types for 88
   country-years, and until 2026-09-09 the deck fitted a per-percentile log-log
   regression on them. That sample does not support this model: **73 of the 88
   pairs compare two DIFFERENT surveys** (usually a household budget survey for
   consumption against EU-SILC for income — checked against PIP's API
   `survey_acronym` field), and EU-SILC reports more at every rank. Fitting the
   profile to them gives a = 1.13, income above consumption at *every* rank,
   crossing at about P12 rather than P79 — contradicting the mechanism the form
   encodes. Restricting to the 15 same-instrument pairs raises R-squared from
   0.42 to 0.90 but leaves the level unchanged, because 9 of those 15 are the
   Philippines, which behaves the same way. And none of the 88 are from
   Sub-Saharan Africa or South Asia, where the mapping is applied; WID's 21
   surveys mostly are.

   Effect on the top-adjusted between-country share, 2023, all four measured
   with the top graft at P95 (the baseline anchor at the time; it is P98 now, so
   the levels sit ~1.3pp higher today while the spread between them stands):
   WID's parameters 54.2%, PIP single-instrument 56.3%, PIP all-88 56.8%,
   superseded regression 55.2% — the parameter choice moves it about 2.6pp,
   against a PIP-vs-WID gap of roughly 16pp on that column.

   The profile is continuous in rank, so unlike the regression — whose
   coefficients existed only per percentile — it needs no special handling for
   the ten 0.1% bins above P99.

   **A second method, run in parallel (2026-09-21; re-fitted at 2021 PPP 2026-09-22) — the
   Wollburg et al. model.** The profile above was estimated on *pre-tax* income, while
   PIP's income countries report *disposable* income. To study that concept gap,
   `consinc.py` also carries the inverse of the consumption model of Wollburg,
   Hallegatte & Mahler (2023, World Bank PRWP 10318, appendix A),

   `ln(con_p) = ln(inc_p^a + γ)`, `γ = g0 + g1 · ln(inc_median)`

   — two 3-parameter log-normals: `a` is the ratio of the spreads (how much more
   compressed consumption is than income) and γ a *consumption floor* that rises with a
   country's median income. The paper fitted it on PIP's dual surveys in 2017 PPP $/day and
   reported a = 0.93, g0 = 0.68, g1 = 0.26 (adj. R² 0.965). Those constants are **not**
   scale-free, so they do not belong on the deck's 2021-PPP bins; `35_fit_consinc_wb.py`
   re-runs the paper's exercise on today's PIP catalog — all 88 national country-years with
   both welfare types (19 countries: the paper's 16 plus Kosovo, Saint Lucia and Turkey),
   income and consumption bin averages at the same percentile, the median income as the deck
   computes it, nonlinear least squares in logs — at both price bases, and writes
   `data/processed/consinc_wb_fit.json`.

   **Weighting decides whether the paper comes back.** With every country-year weighted
   equally, the 2017-PPP fit is a = 0.905, g0 = 0.363, g1 = 0.334 (adj. R² 0.928) — Poland
   alone is 17 of the 88 country-years, Romania 13. With every *country* weighted equally it
   is a = 0.929, g0 = 0.612, g1 = 0.381, with weighted fit statistics of 0.966 (and 0.66 below
   the poverty line): the paper's exponent and the paper's R². g0 and g1 trade off
   (correlation −0.9), so the floor they imply agrees better than the two numbers do. **The
   deck uses the country-balanced fit at 2021 PPP: a = 0.932, g0 = 0.632, g1 = 0.411** —
   the deck's own estimate of the paper's model, and described as such; the paper's
   constants stay in `consinc.py` as `WB_PAPER_2017` for reference, and
   `python data/scripts/consinc.py` asserts the hardcoded constants against the results file.
   Inverted per country-year on the 100-bin grid, `inc_p = (con_p − γ)^(1/a)` with the median
   income solved from the median bin (a unique root), **floored at $0.28/day** — PIP's own
   bottom code — where consumption sits at or below γ (2023: 394 bins in 61 of the 103
   consumption countries; South Sudan 27, Zambia 26, Mozambique 23, DR Congo 23, Central
   African Republic 18).

   Its one clear advantage is the income concept: PIP's own disposable income. Its caveats
   are the ones this note already makes: it is fitted in the *other* direction (inverting
   E[con | inc] is not E[inc | con]), and on the European-heavy PIP dual sample rejected above
   as an estimation sample — nothing from Sub-Saharan Africa or South Asia, where it is
   applied. In-sample, on the deck's 19 cached dual surveys, the inverse predicts PIP's income
   percentiles from consumption far better than the WID profile (median log-RMSE 0.27 vs 0.45;
   predicted/actual 0.92 vs 0.75; bottom five percentiles on target vs −44%; top five +9% vs
   +6%) — but that sample is the paper's own. Against the baseline in 2023, across the 103
   consumption countries: median Gini 0.463 vs 0.478 (PIP as published 0.360), top-10% share
   34.3% vs 36.5%, top-1% 8.4% vs 9.5%, country means within 2% of consumption in the median
   (range 0.79–1.26); the top-1% gate leaves the same four countries unadjusted. **It is never
   the bridging column**: the series `PIP_consinc_wb` and `PIP_topadj_wb` (the same top-1%
   append on it, gate decided per chain) exist only on the reference-year dataset and the
   year-vs-year scatters (appendix slides), where the PIP dropdown offers them.

6. **The top adjustment is a choice, and the deck's baseline is one of six.**
   PIP's surveys are thought to under-capture top incomes, so the deck adds a
   deliberately generous allowance for the missing top — assuming WID is right
   about the top and asking what PIP would then look like. Two methods x three
   anchors (`topadj.py`, tabulated by `30_fig_topadj_sensitivity.py`):

   - **graft** — above the anchor, incomes follow the *shape* of WID's post-tax
     distribution, anchored at PIP's own level in the anchor bin:
     `adj(Py) = base(Px) * WID(Py) / WID(Px)`. The resulting top share follows.
   - **share match** — WID's ten top-1% sub-shares are imposed exactly and the
     shape follows. Closed form: `Y' = A/(1-S)` where A is income at or below
     the anchor and S the imposed top share.

   Anchors P95, P98, P99 (anchor bin `p{n-1}p{n}`, first adjusted bin `p{n}p{n+1}`).
   Both methods are uniform rescalings of WID's top; they differ only in the
   scale factor, which is why countries where PIP sits far below WID at the
   anchor (India) move a lot between the two and countries where it does not
   (the UK) barely move.

   **The deck's baseline is the graft at P98** (Joe's call, 2026-09-09; it was
   P95 before). It lives in **`etl_source.TOPADJ_SPLICE_PERCENTILE`**, and every
   figure that shows `PIP_topadj` — or `WID_posttax_rescaled`, whose country
   means are forced onto it — reads it from there. Anchoring later is the more
   conservative allowance: PIP falls further below WID the higher up you look,
   so a later anchor means a smaller scale factor and a lower grafted top.

   Global MLD, 2023, across the six (base = income basis, 0.349 within / 58.1%
   between):

   | method | anchor | within | between share | median top-1% multiplier |
   |---|---|---|---|---|
   | graft | P95 | 0.417 | 54.2% | 1.79 |
   | graft | **P98** | **0.394** | **55.5%** | **1.45** |
   | graft | P99 | 0.387 | 55.9% | 1.34 |
   | share | P95 | 0.500 | 47.7% | 1.97 |
   | share | P98 | 0.460 | 50.7% | 1.92 |
   | share | P99 | 0.439 | 52.1% | 1.88 |

   So the baseline is **not** an upper bound on the six — share matching at P95
   is. Any claim of the form "even with a generous allowance for the missing
   top…" should be read against this table, not against the baseline alone.

   Crossed with the three consumption -> income slopes of caveat 5 (18 cells,
   `32_fig_consinc_topadj_cross.py`) the between share spans **46.4%–58.0%** and
   the within component **0.360–0.523** — against PIP as published at 69.2% /
   0.214 and WID post-tax per capita at 38.7% / 0.615. Neither modelling choice,
   nor both together, closes the gap between the sources.

7. **Top-end resolution.** Both sources are on the same 109-bin structure:
   99 one-percent bins, nine 0.1% bins across p99–p99.9, and the top 0.1%.
   PIP's 1000 equal bins nest exactly into this, so the aggregation
   (03_harmonize.py) introduces no approximation error. *(The old project
   aggregated PIP to 101 bins, with a coarser top than WID — fixed here.)*

   **Since 2026-09-09 the deck's ANALYTICAL grid is 100 percentile bins.**
   `etl_source.load_bins()` collapses those ten top bins into one 1%-wide bin at
   their population-weighted mean, before anything else is built, so every series
   it returns sits on a plain percentile grid (`etl_source.DECK_BINS`). The raw
   `etl_source.load()` still returns the ETL's own 109 bins, and anything
   genuinely about the top 0.1% — `24_fig_top_of_distribution_from_etl.py` —
   reads that instead.

   Measured cost, on both grids before the change: at most **0.3pp** on any
   between share, and the between components not at all — aggregation preserves
   each country's total income and population, so country means and top-1% shares
   are untouched by construction. Only dispersion inside the top 1% is given up.
   Country Ginis computed from bins move by at most 0.0006 (median 0.0001) between
   the two grids — measured 2026-09-21; an earlier version of this note said ~0.03,
   which was wrong — and every Gini the deck displays comes from the sources' own
   published values, not from bins. Against PIP's published survey-year Gini, a
   bins-based Gini is lower by a median 0.0006; 116 of 2,200 survey country-years
   are more than 0.005 away and 21 more than 0.01, the worst Malawi 1997 (−0.063) —
   the thousand bins are a lined-up distribution, not the survey microdata, so a
   few country-years genuinely differ. Top-1% shares are within 1pp for 99.4% of
   survey country-years. (`refyears.py`, `33_reference_year_indicators.py`.)

   One consequence worth knowing: **select by rank window, never by bin label.**
   A label lookup assumes both the grid and that a label describes the rank,
   which stops being true for a re-ranked series.
   `21_fig_bridging_from_etl.py`'s `rank_window()` is the pattern.
8. **2023 only, extrapolations included.** The WID pull is a single year;
   surveys underlying both sources are often older and extrapolated to 2023
   by the source. A time-series extension means re-running the fetch with
   more years and revisiting file layouts.

## Provenance

- **PIP**: World Bank Poverty & Inequality Platform "thousand bins"
  distribution, via the [OWID catalog](https://catalog.ourworldindata.org/)
  (`garden/wb/2025-10-13/thousand_bins_distribution`). 1000 bins × 0.1% of
  population per country-year; daily income per capita, 2021 PPP $.
- **WID**: [wid.world](https://wid.world) API via the Stata `wid` command.
  Indicators `aptinc/sptinc` (pre-tax national income) and `adiinc/sdiinc`
  (post-tax national income), ages 992 (adults), population `j` (equal-split
  adults), year 2023; `xlcusp` PPP factors; `npopul` ages 992/999 population.
- **Country mapping**: `raw/wid/country_mapping.csv` maps WID 2-letter codes
  to PIP country names (216 entries; the 211 with a PIP counterpart are
  fetched). Note: GG maps to "Channel Islands" (a fixed earlier bug had it
  as Germany).

## History

This pipeline was "re-potted" (2026-08-10) from an exploratory research
project (`~/Documents/GitHub/data_work/global_inequality_pip_wid`), keeping
its battle-tested WID fetcher and verified transformation logic, re-run and
re-verified end-to-end from the cached raw data. The new outputs match the
old project's post-bug-fix files to machine precision, except for the
deliberate improvements noted in the caveats above. The old project also
contains analysis scripts (MLD decompositions, counterfactuals, etc.) that
have NOT been migrated — analyses for this deck are built fresh against the
harmonized file.
