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
> # Only while a future ETL pull request that changes these datasets is still open:
> python data/scripts/refresh_from_etl.py --staging <owid/etl branch name>
>
> # Change nothing, just report whether the committed figures are stale:
> python data/scripts/refresh_from_etl.py --check
> ```
>
> Then **commit `data/raw/etl/` and `data/figures/` together**. `--check` rebuilds
> into a temporary directory, restores the committed figures whatever happens, and
> exits non-zero when they no longer match the ETL — so it is safe to run any time
> and works as a pre-talk sanity check.
>
> It runs the cache refresh and all eight figure scripts in dependency order. Running
> them by hand still works if you need one in isolation:
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
> ```
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
`average` is mean **daily** income in the bin, in PPP international dollars
(PIP: 2021 PPPs; WID: 2023 PPPs — see caveats). `pop` is the number of people
(or adults, for per-adult series) in the bin. `share` is the bin's share of
the country's total income.

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
(`topadj.py` — the top-adjusted PIP series; `rescale.py` — WID post-tax
rescaled to the ADJUSTED PIP country means (`mean_source="PIP_topadj"`, so
the WID-side and PIP-side ladders meet at identical country means — and
therefore identical between components); `consinc.py` — PIP adjusted to an income
basis via the dual-country regression fitted by `04_fit_consinc.py`) so
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
3. **PPP vintages differ.** PIP uses 2021 PPPs; the WID conversion factors
   (`xlcusp`) are for 2023. Level comparisons between sources inherit this.
4. **Zero incomes.** WID has some bins with exactly zero income (as of the
   2026-08 pull: 921 pre-tax, 187 post-tax — bottom percentiles in most
   countries); PIP has none. They
   are **retained** in the harmonized file. Any log-based measure (e.g. MLD)
   must decide how to treat them — that's an analysis-stage decision. The old
   project's convention was to replace zeros with $0.01/day and its
   sensitivity analysis found the choice shifts the between-country share by
   ~3 pp; whatever convention an analysis uses must be stated in its script.
   Note the floor is a single nominal constant ($0.01), so it interacts
   slightly with derived series that rescale incomes (see rescale.py's
   "known, accepted artifact" note).
5. **Top-end resolution.** Both sources are on the same 109-bin structure:
   99 one-percent bins, nine 0.1% bins across p99–p99.9, and the top 0.1%.
   PIP's 1000 equal bins nest exactly into this, so the aggregation
   (03_harmonize.py) introduces no approximation error. *(The old project
   aggregated PIP to 101 bins, with a coarser top than WID — fixed here.)*
6. **2023 only, extrapolations included.** The WID pull is a single year;
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
