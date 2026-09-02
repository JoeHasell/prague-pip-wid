# PROJECT NOTES — "prague-pip-wid" deck

> Handoff notes for a future session. Read [`CLAUDE.md`](CLAUDE.md) first (how to
> work in this repo), then this file, then `README.md` for the framework mechanics
> and `data/README.md` for the pipeline. Last updated: 2026-09-02 (migrated from
> Claude Cowork to Claude Code; slide inventory and git protocol refreshed; inventory
> renumbered for the ETL-sourced deck, 60 slides).

## ⚠️ Refreshing the data after an ETL change

The figures are committed JSON built from a cached ETL extract; nothing in this repo
watches the ETL. After any ETL change, and before presenting, run:

```bash
# reads the public OWID catalog (owid/etl#6764 merged 2026-09-02); no VPN needed:
python data/scripts/refresh_from_etl.py

# only while a future ETL pull request that changes these datasets is still open:
python data/scripts/refresh_from_etl.py --staging <owid/etl branch name>
```

Commit `data/raw/etl/` and `data/figures/` together. `python data/scripts/refresh_from_etl.py --check`
reports staleness without changing anything (non-zero exit when the figures are behind).

Full detail, including the `ETL_VERSION` pin the refresh cannot check for you, in
[`data/README.md`](data/README.md).

## 1. What this is

An interactive, static HTML **slide deck** for a talk (in Prague) by **Joe Hasell
(Our World in Data)** on **global income inequality**, framed as *triangulating
between the two main data sources*:

- **PIP** — the World Bank's *Poverty and Inequality Platform* (survey-based;
  disposable income / consumption, per capita).
- **WID** — the *World Inequality Database* (wid.world; combines surveys, tax
  data, national accounts; national income, per adult; pre- and post-tax).

The talk is organised around three questions:

- **Q1. Is income inequality rising basically everywhere?** (PIP: broadly no; WID: yes)
- **Q2. Which is bigger — inequality *between* countries or *within*?** (PIP: between; WID: within)
- **Q3. Who are the richest 1%?**

Joe authors the substantive content himself; the assistant's role is **scaffolding
and mechanics**: building interactive chart components, wiring data from OWID,
extending the editor, and keeping `slides.json` valid — *not* inventing the
narrative or picking data without being asked.

## 2. The framework (quick version; full detail in README.md)

Static, no-build deck styled after ourworldindata.org (Playfair Display headings,
Lato body, navy palette, 4px red progress stripe). Fixed **1280×720** stage,
scaled to the window.

- **`content/slides.json` is the single source of truth.** Each slide = ordered
  list of **blocks**: `html` (rich text), `component` (interactive module by name
  + `props`), `row` (side-by-side). Slides may also carry an **`annotations`**
  array (drawing layer — see §8).
- **Components** are self-contained JS files in `components/`, registered by name
  and listed in `components/manifest.json`. Pattern:
  `Deck.registerComponent('name', (el, props, ctx) => { ...build DOM in el...; return cleanupFn })`.
  One file may register several components.
- **Editing:** open `?edit` for the in-browser point-and-click editor
  (`src/editor.js`). It writes `slides.json` back through the dev server.
- **Publishing:** `git push` → Netlify serves the static files. No build step.

## 3. How we work together (OPERATIONAL PROTOCOL — important for a fresh session)

**This project moved from Claude Cowork to Claude Code on 2026-09-02, and every
session runs LOCALLY on Joe's Mac.** The Cowork-era protocol (the
`mcp__remote-devices__*` file bridge, staging into `/mnt/user-data/uploads`,
`device_commit_files` with `expectedMtimeMs`, and the hard rule "the assistant
must never run git") is **obsolete**. [`CLAUDE.md`](CLAUDE.md) holds the current
rules; the essentials:

- **Sessions are LOCAL** — in the desktop app's **Code** tab, Environment =
  **Local**, project folder `~/Documents/Claude/Projects/prague-pip-wid`. Claude
  reads and writes Joe's actual working copy, exactly as Cowork did.
- **Git: work on `main`; Claude edits, Joe commits and pushes** from **GitHub
  Desktop** (his credentials live there). Claude leaves its work uncommitted for
  Joe to review, uses read-only `git` freely to orient, and doesn't commit, push
  or branch unless asked. Full rules in [`CLAUDE.md`](CLAUDE.md).
- **Cloud sessions are not used here** (decided 2026-09-02). A cloud container
  can't reach the Mac, so it can't see Joe's browser edits, and Stata — hence
  `00_fetch_wid.py` — exists only on the Mac. A SessionStart hook that set up
  cloud containers was added on 2026-09-02 and **removed the same day**: there is
  no `.claude/` directory, and these docs deliberately no longer branch on
  local-vs-cloud. Don't reintroduce either.
- **Stata is only on the Mac**, so `00_fetch_wid.py` can only run here.
- **The two-writer trap:** the `?edit` editor holds the whole
  deck in the tab and writes the *whole file* on Save, so if Claude edits
  `slides.json` while an older tab is open, Joe's next Save silently reverts it —
  no conflict, no warning. **After Claude touches `slides.json`, Joe reloads the
  browser before his next edit**, and Claude says so in its reply. Claude edits
  that file surgically, never regenerating it wholesale.
- `src/*`, `components/*` and `data/*` are Claude-only in practice (the browser
  editor writes `slides.json` alone), so those never collide.
- **Note on `src/` changes:** editing `src/deck.js`, `src/editor.js` or the CSS
  requires Joe to **restart the dev server + hard-refresh**. `slides.json`-only
  changes need just a reload. In a local session, if `:4173` is already answering
  it's Joe's dev server — use it, don't kill it, don't start a second one.
- **When Claude adds a NEW file** (e.g. anything under `content/images/`), say so
  explicitly in the reply — a missing image breaks the slide for everyone else.

## 4. Current state of the deck (as of 2026-09-02)

**60 slides in three groups**, all in the one `slides.json`. Group A is the live
work; B and C are older material kept in the same file.

- **A. 1–22 — the SHORT (15 min) talk, actively being drafted.** Narrowed to Q2
  alone: the two sources' opposite answers, the MLD, why surveys and DINA
  disagree, the bridging chain, and the survey/national-accounts income gap.
- **B. 23–52 — the FULL (60 min) talk**, the earlier and broader draft: Q1 → Q2
  → Q3, then a reading list. On this branch the three hand-drawn reference-year
  sketches are retired and six chart slides (32–37) plus a between-share trend
  slide (45) take their place; `main` still carries the sketches.
- **C. 53–60 — original template demo slides** ("How to edit…", the three
  `demo-*` components). Leftover; safe to delete when Joe says so.

**Figures are shared between A and B** — e.g. `fig-raw-comparison` appears in
both — so editing a figure script or component changes both talks. Check where
else a figure is used before adjusting it for one slide.

### A. The short (15 min) talk — 1–22

| # | id | what it is |
|---|----|-----------|
| 1 | slide-title-short | Title (`layout:title`): "Where does global inequality lie: between or within countries?" [DRAFT] — Hasell, Arriagada, Rohenkohl |
| 2–3 | slide-owid-role, slide-g61p1r | About OWID — its role, and the case that better *presentation* of inequality data could unlock public value |
| 4 | slide-two-sides | "The two main sources give opposite answers": WID 32% between-country (Chancel & Piketty 2021) vs World Bank 65% (2013). Uses both images in `content/images/` |
| 5 | slide-4ovt9k | Mean Log Deviation — why the literature uses it (decomposability) and the normative choice that hides |
| 6–7 | slide-f85v2c, slide-vk8p9y | "Why do survey data and DINA disagree?" — measurement vs concept. 7 duplicates 6 and adds 2 annotations |
| 8 | slide-16foo7 | "'Survey income' is the more relevant concept here" (Anand & Segal; contra Sala-i-Martin) |
| 9 | slide-s64zud | "Bridging" — can we keep the survey income concept while addressing its accuracy? |
| 10 | slide-xdr0fh | Raw WID-vs-PIP comparison, 3 countries: P10/P90/mean lollipops + between/within MLD bars. `fig-raw-comparison {title:""}` |
| 11–15 | slide-bridge-step1 … slide-bridge-step5 | **Progressive reveal** of the bridging chain over the same 3-country figure — each slide adds one series through the `reveal` prop (pre-tax/adult + PIP → +pre-tax/capita → +post-tax → +rescaled → +top-adjusted & consinc) |
| 16–17 | slide-bridging-all-nomid, slide-2ewkz8 | The same chain for **all countries** (`dataUrl: data/figures/fig_bridging_all.json`); 16 reveals a subset, 17 shows every series |
| 18 | slide-epyx2y | "How does survey/NA ratio vary with income?" — Deaton, early Milanovic, Concept-2 inequality |
| 19–20 | slide-means-share-plain, slide-means-share | Survey mean as a **share of WID national income**, 2023, Venezuela hidden. 19 is stripped back (`bubbles:false`, unweighted fit only); 20 adds population bubbles and both fits. `fig-means-scatter` |
| 21 | slide-m203r4 | The 3-country bridging figure again, all series shown (same props as 41) |
| 22 | slide-means-share-1990 | The same share chart for **1990**, the start of the PIP record |

### B. The full (60 min) talk — 23–52

| # | id | what it is |
|---|----|-----------|
| 23 | slide-title-full | Full-talk title (`layout:title`): "What do we know about global income inequality?" [DRAFT] |
| 24 | slide-title | Earlier title slide, same heading — superseded by 23 |
| 25 | slide-rmm9en | Overview: the three questions and the two sources |
| 26 | slide-52qg9a | "Three basic questions" — a `deck-table small` comparing PIP / WID headlines / triangulated across Q1–Q3 plus income concept, sources, measure, strengths, weaknesses. **Q3 row still has `??` cells** |
| 27 | slide-scatter-gw | **Q1** scatter: PIP Gini (x) vs WID pre-tax Gini (y), ~2019, colour by WB region, 45° line — "inequality is a lot higher in WID". `gini-pip-wid-scatter {}` |
| 28 | slide-scatter-gw-post | Same scatter, WID **post-tax** — `{measure:"posttax"}`. Flick 27↔28 to watch the cloud drop toward the diagonal |
| 29 | slide-scatter-gw-reg | Post-tax with **register-income countries highlighted** — `{measure:"posttax", highlightGroup:"register"}` (1 annotation) |
| 30 | slide-riurji | **Two-panel** 1993-vs-2019 scatter (PIP left, WID right), 45°=no change; metric radio. `ineq-trend-scatter {metrics:["gini","top10","palma","top1"]}` |
| 31 | slide-qs05wh | **Change-vs-change**: Δ PIP (x) vs Δ WID (y); metric + abs/rel radios. `ineq-change-scatter {}` |
| 32–33 | slide-q1refyear-counts, slide-q1refyear-counts-obs | **Varying the reference year, 1:** how many countries' Gini is rising / falling / stable, by reference year. `fig-reference-year-composition {metrics:["gini"]}`. 33 is the observed-data twin (`dataUrl: fig_reference_year_observed.json` — each country's nearest actual survey within five years, so coverage is smaller) |
| 34–35 | slide-q1refyear-alpha, slide-q1refyear-alpha-obs | **Varying the reference year, 2:** the same counts with the GE-α measure selector live. `fig-reference-year-composition {}`; 35 is the observed-data twin |
| 36–37 | slide-q1refyear-change, slide-q1refyear-change-obs | **Varying the reference year, 3:** average change by reference year, unweighted and population-weighted. `fig-reference-year-change {}`; 37 is the observed-data twin. These six replace the three hand-drawn sketches that `main` still carries at 32–34 |
| 38 | slide-yp4gbg | **Q2** section opener |
| 39 | slide-q2rawcmp | Raw 3-country comparison (same figure as 10) |
| 40 | slide-q2mldex | Anatomy of the MLD decomposition. `fig-mld-decomp {}` |
| 41 | slide-q2bridge | 3-country bridging chain, all series (same as 21) |
| 42 | slide-q2consinc | Consumption→income mapping explainer, per-country fits. `fig-consinc-explainer {}` |
| 43 | slide-q2topadjex | Top-adjusted PIP series explainer (kept below P95, replaced above). `fig-topadj-explainer {}` |
| 44 | slide-q2bridgeall | All-country bridging chain (same as 17) |
| 45 | slide-q2trend | **Between-country share of global MLD, 1990–2024**, one line per series, measure selector (between share, or the MLD components), 2023–24 shaded as mostly extrapolated/nowcast. `fig-between-share-trend {dataUrl: fig_between_share_trend.json, sources:[…]}` |
| 46 | slide-r2fdmx | **Q3** section opener: "Who are the richest 1% in the world?" |
| 47 | slide-q3thresh | Top-1% income thresholds by source. `fig-top-thresholds {title:""}` |
| 48–49 | slide-q3treepip, slide-q3treewid | Treemaps of who the global top 1% are — PIP vs WID post-tax per capita. `fig-top1-treemap {source:…}` |
| 50 | slide-ct1u0k | Q3 placeholder — still template text |
| 51–52 | slide-tjof1k, slide-3382ld | Literature review / reading list (51 is an empty stub; 52 has the actual list) |

### C. Template demo slides — 53–60

`slide-ers737`, `slide-model`, `slide-chart`, `slide-1kotk6`, `slide-table`,
`slide-row`, `slide-editing`, `slide-publish`. The "How to edit…" walkthrough
that shipped with the framework, plus the only slides using the three `demo-*`
components (55 line chart, 57 sortable table, 58 row + scrubber).

## 5. Components built

Registered in `components/manifest.json`: `gini-pip-wid-scatter.js`,
`ineq-trend.js`, the **nine** `fig-*.js` figure files, plus the three
`demo-*.js`. Newest: **`fig-means-scatter.js`** (added 2026-08-27, slides 19/20/22)
— survey mean vs WID national-income mean, one dot per country, with
`mode` (`levels`/`ratio`/`share`), `year` (`2023`/`1990`), `hide`, `yDomain`,
`bubbles` and `fits` props; **`fig-reference-year-trends.js`** (2026-08-26,
slides 32–37; registers `fig-reference-year-composition` and
`fig-reference-year-change`); and **`fig-between-share-trend.js`** (2026-09-02,
slide 45). `fig-raw-comparison.js` also gained a **`reveal`** prop for building a
figure up across consecutive slides (short talk, 11–17).

One convention, since 2026-08-26: **every chart component fetches a
`data/figures/fig_*.json`**, generated by a numbered script in `data/scripts/`,
and no component JS holds a data array. `gini-pip-wid-scatter.js` and
`ineq-trend.js` used to embed theirs; they now read `fig_gini_scatter.json` and
`fig_ineq_trend.json`, built by `25_fig_scatters_from_etl.py` from the ETL's
cross-source comparison dataset (the `2N_*.py` scripts read the ETL cache in
`data/raw/etl/`; the `1N_fig_*.py` scripts are the local-pipeline originals). The
per-figure table (script → figure → component) lives in `data/README.md`; don't
duplicate it here.

### `gini-pip-wid-scatter` (file: `gini-pip-wid-scatter.js`)
One dot per country, PIP Gini (x) vs WID Gini (y), ~2019 reference year, colour by
**World Bank PIP region** (Okabe-Ito colourblind-safe palette), 45° "sources
agree" line, hover tooltips. **72 countries**, read from `data/figures/fig_gini_scatter.json` as
`[{c, p (pip gini), wPre (wid pretax), wPost (wid posttax), r (region), y (year)}]`.
Props (all optional):
- `measure`: `"pretax"` (default) or `"posttax"` — which WID series on Y. Axes are
  identical for both so slides 27/28 flick cleanly.
- `highlight`: array of country names to keep in colour (others faded); or
  `highlightGroup:"register"` for the built-in register list.
- `title`, `yLabel`, `source`, `min`, `max` (axis domain, default 0.2–0.8), `data`.

### `ineq-trend.js` — registers TWO components (shares one embedded dataset)
Data (`data/figures/fig_ineq_trend.json`): **115 countries**, `[{c, r (WB region), <metric>_<pip|wid><93|19>}]`
where metric ∈ {`gini`, `top10`, `palma`, `top1`}. Note **`top1` (top-1% share)
exists for WID only** (all `top1_pip*` are null) — PIP has no top-1% series.
- **`ineq-trend-scatter`** (slide 30): two panels (PIP left, WID right), each a
  scatter of a country's inequality in **1993 (x) vs 2019 (y)**; 45°=no change.
  Prop `metrics` (default `["gini","top10","palma"]`; slide 30 adds `"top1"`),
  `metric` (default first). Uses **max coverage per source** (97 PIP / 90 WID for
  Gini/Top10/Palma; 0 PIP / 90 WID for Top1 → PIP panel intentionally blank).
- **`ineq-change-scatter`** (slide 31): one scatter, **Δ PIP (x) vs Δ WID (y)** with
  zero quadrant lines + 45° agreement line. Props `metrics`, `metric`, `mode`
  (`"abs"` default | `"rel"`). Uses the **72-country intersection** (both sources,
  both years). `abs` = 2019−1993 in metric units; `rel` = (2019−1993)/1993 ×100%.

### CSS conventions (in `src/deck.css`)
- Tables in text blocks: `<table class="deck-table">` (add `small` for compact
  font) → OWID-styled, and stay click-to-edit in `?edit`.

## 6. Data provenance (so a future chat can reproduce / extend)

All data is from **Our World in Data**. Since 2026-08-26 it reaches the deck
through `data/scripts/refresh_from_etl.py` (see the top of this file), which reads
parquet/feather straight off the public catalog; the notes below record where each
series sits in that catalog.

**Primary comparison dataset** (basis of the Q1 slides, 27–31):
```
grapher/poverty_inequality/2025-01-22/inequality_comparison/inequality_comparison
```
Columns follow the pattern:
```
{metric}_{source}__ref_year_{1993|2019}__reference_years_1993_2019__only_all_series_{variant}
  metric  : gini | p90p100share (=top 10% share) | palmaratio | p99p100share (=top 1%, WID ONLY)
  source  : pip_disposable_percapita | wid_pretaxnational_peradult
  variant : all_data_points | only_countries_in_all_sources
```
- **Gotcha:** the 1993 and 2019 values sit on *different `year` rows* for each
  country. Collapse to one row per country first: `df.groupby("country").max(numeric_only=True)`, then read the 1993 and 2019 columns.
- Coverage (Gini/Top10/Palma): 97 countries with both years for PIP, 90 for WID,
  **72 with both sources & both years** (= the `only_countries_in_all_sources`
  set). Top-1%: 90 WID, 0 PIP.
- Slides 27–29 use the **~2019** point where both sources exist → **72 countries**
  (58 until 2026-08-26, when the per-country collapse above was applied before
  intersecting the two sources — China, Indonesia and Russia were among the missing).

**Post-tax WID** (slides 28/29, `posttax`): the comparison dataset only has pre-tax
WID, so post-tax comes from the main WID dataset:
```
grapher/wid/2026-06-18/world_inequality_database/inequality
  gini__welfare_type_before_tax__extrapolated_yes   # = pre-tax national income; reproduces the comparison pre-tax values EXACTLY at the same country-years (verified)
  gini__welfare_type_after_tax__extrapolated_yes    # = POST-TAX national income (used for `posttax`)
  gini__welfare_type_after_tax_disposable__...       # alt: post-tax DISPOSABLE income (not yet used; offered as a future option)
```
So slides 27→28 differ *only* in tax treatment (national income, per adult, same
countries/years). Post-tax narrows the mean WID−PIP gap from ≈0.18 to ≈0.12.

**Regions:** World Bank PIP `region_name` from
`grapher/wb/2025-04-14/world_bank_pip/world_bank_pip#region_name__poverty_line_no_poverty_line__welfare_type_income_or_consumption__table_income_or_consumption_consolidated__survey_comparability_no_spells`
(7 groups incl. the non-geographic "Other high income countries"). An alternative
continent mapping is `continents-according-to-our-world-in-data` (`owid_region`).

**Units:** Gini 0–1; top-10% / top-1% shares in %; Palma is a ratio (~0.8–3+).

**Where the data currently lives:** `data/figures/fig_gini_scatter.json` and
`data/figures/fig_ineq_trend.json`, rebuilt by `25_fig_scatters_from_etl.py` on
every refresh. The component JS holds no data arrays.

## 7. Colour / dataviz conventions

- Region colours use the **Okabe-Ito** colourblind-safe palette
  (`#0072B2, #E69F00, #009E73, #CC79A7, #56B4E9, #D55E00, #7A3E9D`).
- Categorical palettes were validated with the **dataviz skill's**
  `scripts/validate_palette.js` (run it; don't eyeball). Okabe-Ito passes all hard
  gates for the 6 regions; one pair sits in the CVD "floor" band, covered by the
  legend + hover labels. (Optional future improvement: per-region marker *shapes*
  as a second channel.)

## 8. The annotation / draw layer (added to the engine)

A slide-level drawing overlay for sketching charts and dropping movable labels,
usable on **any** slide (including over live charts). Implemented in `deck.js`
(rendering, both view + edit) and `editor.js` (the tools).

**Schema** — `slide.annotations` = array of items in **stage coords (0–1280 ×
0–720)**:
```
{id, type:"pen",  pts:[[x,y],...], color, width}
{id, type:"line", x1,y1,x2,y2, arrow:true|false, color, width}
{id, type:"text", x, y, text, color, size}
```
Rendered by `deck.js` `annotMarkup()`/`makeAnnotLayer()` into an `<svg
class="slide-annot">` overlay (pen paths are lightly smoothed via `penPath()`).
`Deck.renderAnnotations()` re-renders the active slide's overlay.

**Editor "Draw" toolbar group:** Select (move/drag/delete, dbl-click text to
re-edit), Pen, Line/arrow, Text, Undo (last mark on slide), Clear (slide). A
floating palette (colours / pen widths / S-M-L text sizes / arrowhead toggle)
appears when a draw tool is active. Toggle a tool off (click again or Esc) to
return to normal block editing. Coordinate mapping uses the SVG's
`getScreenCTM()`.

**Known v1 limits:** selecting a thin pen/line means clicking on the stroke
(text is the easy target); dragging moves a whole mark, not individual endpoints.
Freehand sketches store many points, so heavy drawing inflates `slides.json`
(the sketch slides pushed the file past 500 KB — normal, just noticeable).

## 9. Environment & verification recipes

Full detail in `CLAUDE.md`. Everything runs on Joe's Mac.

- **It's his machine, not a clean container:** **Python 3.9.7**, **Node v16.9.1**
  (checked 2026-09-02) — write pipeline scripts for Python 3.9. pandas and pyarrow
  are installed; check before assuming anything else is, prefer
  `pip install -r data/requirements.txt` over ad-hoc installs, and don't install
  things without asking. **Stata lives here**, so this is the only place
  `00_fetch_wid.py` can run (still ~1–2 h; don't run it casually).
  If `:4173` already answers, that's Joe's dev server — use it, don't kill it.
- The catalog fetches read parquet/feather straight off
  `catalog.ourworldindata.org` — the `owid-catalog` library is **not** needed.
- **Render harness = the built-in browser pane** pointed at the dev server. There
  is **no Playwright or Chromium on the Mac** (they belonged to the deleted cloud
  hook) — don't install any; the pane needs nothing:
  `preview_start` → `http://localhost:4173/#<N>`, `resize_window` to 1280×720 for
  a 1:1 stage, `screenshot` (returns 800×450, faithful for layout; `zoom` for
  detail), `javascript_tool` to poke `Deck.data` or fire events for radios /
  dropdowns / draw tools, `?edit` in the URL for editor tools, and
  `resize_window` preset `desktop` when done. Verified end to end 2026-09-02.
  Actually look at the image: the 1280×720 stage does not scroll, so overflow is
  invisible otherwise. Playfair/Lato load normally here (they were blocked in the
  old cloud sandbox).
- **Palette validator**: dataviz skill →
  `node scripts/validate_palette.js "<hex,hex,...>" --mode light --pairs all`.
- Always `node --check` edited JS and `JSON.parse` edited JSON before committing.

## 10. Open threads / next steps

- **Q2 and Q3 are built out** (full talk, slides 39–49: raw comparison, MLD
  explainer, the bridging chain, consumption→income and top-adjustment
  explainers, the between-share trend, top-1% thresholds and treemaps), each
  backed by a `data/scripts/2N_*.py` (reading the ETL cache in `data/raw/etl/`)
  → `data/figures/fig_*.json` → `components/fig-*.js` chain. The method behind
  them — see §12. Joe's prior research project
  (`~/Documents/GitHub/data_work/global_inequality_pip_wid`) was "re-potted":
  its WID fetch + harmonization pipeline now lives in `data/`, verified
  end-to-end, and was then moved into OWID's ETL (owid/etl#6764, merged
  2026-09-02). The figures were first built against
  `data/processed/pip_wid_harmonized_2023.csv`; since 2026-08-26 they come from
  the ETL's `harmonized_income_distributions`, and the `1N_fig_*.py` scripts
  are the reference implementation. The old project's analysis scripts/charts
  were deliberately not migrated (several of its README headline numbers
  predate a critical PPP bug fix and are stale). New chart components must
  fetch their data from per-figure files produced by pipeline scripts — no
  hard-coded data arrays in component JS.
- **DONE 2026-08-27, committed 2026-09-02 — the PPP price-base fix.** WID
  publishes incomes in constant LCU of the *latest database year*, so converting
  them with `xlcusp(2023)` overstated every country by its inflation relative to
  the US over 2023–25 — ~4x for Venezuela, Sudan and Argentina, ~2x for Turkey.
  `config.PPP_YEAR = 2025` now drives the conversion; both processed CSVs and all
  figure JSONs were regenerated and `99_verify.py` passes 19/19. See §12.
- **DONE 2026-08-27 — the survey-vs-national-accounts figure**
  (`17_fig_means_scatter.py` → `fig-means-scatter.js`, slides 19/20/22), the
  project's first two-year figure: `config.COMPARISON_YEAR = 1990` alongside
  `TARGET_YEAR`. The rest of the pipeline stays single-year.
- **OPEN — two reproducibility gaps in that new figure** (found 2026-09-02, Joe's
  call whether to close them):
  - `18_fetch_wid_means.py` is cited three times (`config.py`,
    `17_fig_means_scatter.py`) as the producer of
    `data/raw/wid/WID_national_income_means.csv`, but **the script doesn't
    exist**. The raw file is committed and correct; nothing regenerates it.
  - `01_fetch_pip.py` only ever writes `TARGET_YEAR`, so it **cannot produce**
    the committed `pip_thousand_bins_1990.csv.gz` that `PIP_RAW_FILE_EARLY`
    points at. ~5 lines to loop over both years.
- Editorial TODOs (Joe's call, don't do unprompted): rename `meta.title` (still
  the template's "Deck framework — demo"); give slides 30 & 31 distinct headings
  (both currently under the same Q1 kicker); the slide-26 table's Q3 row still
  has `??` cells; slides 50 and 51 are still placeholders; decide the fate of the
  demo slides (53–60) and the `demo-*` components, and of the superseded title
  slide 24.
- Offered-but-not-built: post-tax **disposable** WID variant (vs national income)
  on slides 28/29; per-region marker shapes for stronger CVD separation; an
  "add row / add column" control for `deck-table` in the editor.

## 11. File map

```
CLAUDE.md               # how Claude works in this repo (read first)
content/slides.json     # all slide content + per-slide annotations (SINGLE SOURCE OF TRUTH)
components/
  manifest.json         # list of component files to load
  gini-pip-wid-scatter.js   # Q1 slides 27–29 scatter (pre/post-tax, region highlight)
  ineq-trend.js             # Q1 slides 30–31 (trend + change scatters; two components)
  fig-*.js                  # Q2/Q3 + short-talk figures — each FETCHES data/figures/fig_*.json
  demo-*.js                 # template demos (used only by demo slides 55/57/58)
data/                   # REPRODUCIBLE DATA PIPELINE (see §12 and data/README.md)
  scripts/              # numbered pipeline steps + verification suite
  raw/                  # committed raw caches (WID API pull, PIP extract)
  processed/            # regenerable outputs incl. pip_wid_harmonized_2023.csv
  figures/              # one fig_*.json per deck figure, fetched by fig-*.js
src/
  deck.js               # engine: render, nav, components, ANNOTATION overlay
  deck.css              # theme + .deck-table + .slide-annot styles
  editor.js             # ?edit editor: text, lists, component props, DRAW tools
  editor.css            # editor chrome + draw palette/tool styles
index.html, dev-server.js, netlify.toml, README.md
data/requirements.txt   # pip install -r data/requirements.txt
PROJECT_NOTES.md        # this file
```

## 12. The data pipeline (added 2026-08-10)

`data/` holds the reproducible pipeline for the Q2 phase (between- vs
within-country inequality), re-potted from Joe's prior research project. Since
2026-08-26 the deck's figures are built from the ETL instead (the refresh section
at the top of this file); this local pipeline is the reference implementation of
the method and still runs. **Read `data/README.md` first** — it documents the
five series, the income concepts, and six known caveats. Key facts for a fresh
session:

- **The dataset everything builds on:**
  `data/processed/pip_wid_harmonized_2023.csv` — PIP + WID full income
  distributions, 2023, identical 109-bin structure for all five series
  (PIP; WID pre-tax & post-tax NATIONAL income, each per adult & per capita).
- **Stage 0 (WID fetch) needs Stata and ~1–2h; never re-run it casually.**
  Everything downstream is pure Python off the committed raw cache
  (`data/raw/wid/`, fetched 2026-02-20). `00_fetch_wid.py --resume` etc.
  A planned re-fetch may add `acainc/scainc` (post-tax DISPOSABLE income —
  closer concept to PIP; note `diinc` is post-tax NATIONAL income, an
  earlier project mislabeled it as disposable).
- **PPP conversion uses `config.PPP_YEAR` (2025), NOT `TARGET_YEAR`**
  (fixed 2026-08-27). WID reports incomes in constant local currency of the
  latest year in the database, so the `xlcusp` factor must come from that
  price-base year; using the data year overstated high-inflation countries
  several-fold. `fetch_ppp.do` fetches both years and `02_process_wid.py`
  selects `PPP_YEAR`. **Re-check this against wid.world's "Prices and currency
  conversions" note after any WID refresh — if the base year moves, `PPP_YEAR`
  moves with it.** Don't "simplify" it back to `TARGET_YEAR`.
- **Always run `python data/scripts/99_verify.py` after touching the
  pipeline** (19 checks; encodes two historical bugs: missing PPP conversion,
  wrong bin population weights).
- **MLD weighting convention:** ALL MLD decompositions weight countries by
  ONE demographic yardstick, MATCHED TO THE SERIES' BASIS (adults for
  per-adult series, total population otherwise — incl. for PIP). Never
  compute an MLD decomposition without it (per-source population weights
  leak WID-vs-PIP demographic disagreements into the between component;
  decided 2026-08-11). The yardstick was WID's demography in the deck's local
  pipeline (`data/scripts/mld.py`); since 2026-09-02 the ETL uses Our World in
  Data's population series for totals and UN World Population Prospects for
  adults aged 20+, independent of both sources, while WID's per-adult series
  are still converted to per capita with WID's own adult share. Measured
  effect on every between share: at most 0.02pp (WID's counts are UN WPP
  too; Togo and France are the only material differences).
- **IMPLEMENTED bridging step "PIP_consinc"** (2026-08-11): PIP adjusted to
  an income basis — consumption countries mapped via per-percentile OLS
  ln(y_p)=alpha_p+beta_p ln(c_p) fitted on PIP's 88 dual country-years
  (04_fit_consinc.py -> processed/consinc_model.csv + raw/pip/
  pip_welfare_types.csv; series built in consinc.py; explainer slide with
  per-country fit charts via 13_fig_consinc_explainer.py). CAVEAT: the
  estimation sample has no SSA/South Asia — out-of-sample transfer. Source
  data verified (2026-08-11):
  `garden/wb/2026-06-26/world_bank_pip/percentiles` in the OWID catalog —
  100 percentiles (avg/thr/share/pop) per country-year-welfare_type, with
  88 national country-years having both income & consumption at 2021 PPPs
  (19 countries; Albania 2016-18 confirmed; Philippines has a long panel).
  Also available: `garden/wb/*/world_bank_pip_legacy/percentiles_income_consumption_*`
  and LIS percentile tables (`garden/lis/2026-06-12/luxembourg_income_study/percentiles`).
- **Zeros are retained** in the harmonized file (921 pre-tax WID bins);
  zero-handling is an analysis-stage decision that each analysis script must
  state explicitly (old convention: replace with $0.01/day; sensitivity ≈3pp
  on the between-country share).
- The verification cross-checked all outputs against the old project's
  post-bug-fix files: exact match, except PIP's top-end bins which now match
  WID's structure exactly (deliberate improvement).
