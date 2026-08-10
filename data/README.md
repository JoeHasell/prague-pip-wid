# Data pipeline: harmonized PIP & WID income distributions

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
```

Each script's docstring documents exactly what it does and why — read those
before changing anything.

## Figure scripts (10+): one script per deck figure

Scripts numbered `10_fig_*.py` and up each produce the data behind ONE deck
figure, written as a small JSON to `data/figures/`. The matching chart
component in `components/` fetches that JSON at runtime — **no numbers are
hard-coded in component JS**. So the provenance chain for any figure is:

```
slide → component (components/fig-*.js) → data/figures/fig_*.json → data/scripts/10+_fig_*.py → processed/ → raw/
```

Method choices that affect a figure's numbers (e.g. zero-income handling for
MLD) are made and documented in the figure script, and echoed in the JSON's
`meta.notes`. After a raw-data refresh, re-run steps 02–03 and then the
figure scripts to regenerate every figure.

| script | figure | slide component |
|---|---|---|
| `10_fig_raw_comparison.py` | Raw WID-vs-PIP comparison, 3 countries: P10/P90/mean lollipops + between/within MLD stacked bars | `fig-raw-comparison` |

## The raw WID data (and how to refresh it)

`raw/wid/` is a **committed cache** of a WID API pull (fetched 2026-02-20,
China re-fetched 2026-03-01). Refreshing it requires **Stata** with the `wid`
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

**Optional for the next re-fetch:** WID also has post-tax **disposable/cash**
income (`cainc`) — conceptually closer to what PIP measures than post-tax
national income. Adding `acainc scainc` to the `indicators()` call in
`00_fetch_wid.py` would fetch it in the same pull.

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
4. **Zero incomes.** WID has 921 pre-tax and 184 post-tax bins with exactly
   zero income (bottom ~5 percentiles in most countries); PIP has none. They
   are **retained** in the harmonized file. Any log-based measure (e.g. MLD)
   must decide how to treat them — that's an analysis-stage decision. The old
   project's convention was to replace zeros with $0.01/day and its
   sensitivity analysis found the choice shifts the between-country share by
   ~3 pp; whatever convention an analysis uses must be stated in its script.
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
