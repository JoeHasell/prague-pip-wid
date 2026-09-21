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

# while an ETL pull request that changes these datasets is still open — and this is
# where the committed figures come from today (owid/etl#6806, the WID 2026-09-02 update):
python data/scripts/refresh_from_etl.py --staging worktree-etl-data-wid-update
```

Until owid/etl#6806 merges the catalog modes stop with an error, because
`etl_source.WID_VERSION` is a version the catalog does not carry yet — use `--staging`,
or `--local <path to an owid/etl checkout>` in which the branch has been built (the
staging server was already gone on 2026-09-21; the committed cache was rebuilt that way).

Commit `data/raw/etl/`, `data/figures/` and `data/processed/reference_year_indicators.csv`
together. `python data/scripts/refresh_from_etl.py --check` reports staleness without
changing anything (non-zero exit when the figures or the dataset are behind).

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
- **Git: two routes.** On Joe's Mac, work on `main` — Claude edits and leaves the
  work uncommitted, Joe commits and pushes from **GitHub Desktop** (his credentials
  live there). From a collaborator's clone, **branches and pull requests against
  this repo are fine**: prague-pip-wid#1 and #2 both landed that way, and a PR is
  the better review surface for a change that rewrites every figure JSON. Either
  way Claude uses read-only `git` freely to orient and doesn't commit, push or open
  a PR unless asked. Full rules in [`CLAUDE.md`](CLAUDE.md).
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
  needs **no dev-server restart** — the server serves from disk, so a reload is
  enough (hard-reload if the browser cached the JS/CSS). These notes and
  CLAUDE.md both used to say a restart was required; it is not, and Joe has had
  to correct it more than once. In a local session, if `:4173` is already
  answering it's Joe's dev server — use it, don't kill it, don't start a second.
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
`demo-*.js`. Newest: **`fig-means-scatter.js`** (added 2026-08-27, slides 19/20/22;
ETL-sourced since 2026-09-02 via `28_fig_means_from_etl.py`)
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
- **DONE 2026-09-21 — reference-year indicators from the ADJUSTED PIP bins.**
  `data/processed/reference_year_indicators.csv`, built by
  `33_reference_year_indicators.py` from two new cache tables
  (`reference_year_bins`, `wid_reference_year_indicators`) and `pip_welfare_basis`,
  with the matcher and the bins-based indicator code in `refyears.py`. It is the
  ETL's `inequality_comparison` method — nearest PIP SURVEY year within ±5 of a
  reference year — applied to every reference year 1990–2024 independently, on
  PIP / PIP_consinc / PIP_topadj (the deck's own chain, so the append top-1% and
  the logit cons→income profile), plus the two WID per-capita series at the
  reference year itself; Gini, top-10% / bottom-40% / top-1% shares, Palma, mean,
  population, all from the bins on the deck's 100-bin grid. Both the reference
  year and the survey year actually used are saved. Ties go to the earlier
  survey and nothing is excluded (the ETL's 1988–89 / 2020–24 exclusions protect
  one 1993/2019 pair; that is a decision for `refyears.pair()`, which also carries
  the ETL's same-welfare rule). Against the ETL's own 1993/2019 output the port
  reproduces the matched years for 95/97 and 97/97 countries; the two residuals
  are countries the ETL re-matches to a same-welfare pair further away, which
  independent matching cannot do. The cache was rebuilt from a local ETL build
  (`--local`, a new source tier) because owid/etl#6806's staging server was gone;
  every pre-existing cache table came back content-identical.
  **Same day, the figure on top of it:** `34_fig_refyear_scatter.py` ships that dataset
  as `data/figures/fig_refyear_scatter.json` and `components/fig-refyear-scatter.js`
  registers `refyear-scatter` (year A vs year B, a PIP panel beside a WID panel) and
  `refyear-change-scatter` (change in PIP vs change in WID), with the years, metric,
  PIP series (as published / income basis / top 1% appended), WID series and the
  same-welfare rule chosen on the slide. Two appendix slides mount them
  (`slide-refyear-scatter`, `slide-refyear-change`, after the between-share trend).
  It generalises the 1993-vs-2019 `ineq-trend` figure to any years and to the
  adjusted PIP; the pairing rules are refyears.pair()'s.
- **DONE 2026-09-09 — the variants slide shows BOTH choices, on one key
  alphabet.** `slide-topadj-variants` splits the cons->income column as well as
  the top-adjusted one, and i/ii/iii now name the same slope in both, so a single
  merged key line serves the whole chart (the component dedupes keys across the
  varied columns rather than repeating a key per column).
  New idea in the JSON: a variant may be marked **`aside`**. It is drawn set
  apart (an 11px gap), carries its OWN value labels inside its segments plus its
  total above, and is left OUT of the labelled range — the range box is centred
  on the run of comparable bars, not on the whole cluster. The one aside variant
  is "NA": the top-1% adjustment applied to raw PIP with no cons->income step,
  which answers a different question from the three slopes beside it and would
  misdescribe the spread if pooled into one min-max.
- **DONE 2026-09-09 — the bridging column is APPEND on the central slope.**
  `etl_source.TOPADJ_METHOD = "append"`, Joe's choice on the merits: the
  under-representation story is the one the deck tells, and it is the only method
  it reports. `PIP_topadj` is therefore append on `PIP_consinc` at b = 0.12,
  which is exactly variant c of the four on the variants slide — asserted by eye
  and by the figure (bar c and the single bars agree to 4dp).
  What moved: PIP top-adjusted within 0.437 -> **0.487**, between 0.478 ->
  **0.465**, total 0.914 -> **0.952**, between share 52.2% -> **48.9%**; WID
  post-tax rescaled 43.8% -> **43.2%**.
  **PIP_topadj IS NOW RAGGED** — 101 bins where adjusted, 100 where the gate
  skipped the country — because append re-reads the survey as the bottom 99% and
  lands at ranks the grid does not have. Three things make that safe:
  (1) its bin LABELS are rewritten to the ranks they actually occupy
  (`p0p0.99`, `p98.01p99`, `p99p100`), so a lookup written for the grid raises
  instead of silently returning a bin a whole percentile off;
  (2) everything that reads it selects by RANK WINDOW (`rank_window`), not label;
  (3) the `load_bins` grid assert exempts exactly this series, and the two
  `decompose` calls that see it pass `expect_bins=None`.
  Every other series, including `WID_posttax_rescaled` (which takes only country
  MEANS from PIP_topadj), stays on the 100-bin grid.
  The rank-window fix earns its keep immediately: the US P90 lollipop is now
  $5,805 rather than the $5,558 a stale label lookup would have given — the 4.4%
  error predicted before the switch.
- **DONE 2026-09-09 — the deck's analytical grid is 100 PERCENTILE BINS.**
  Joe's call, after measuring the cost on both grids first.
  `etl_source.load_bins()` collapses the ETL's ten 0.1% bins across the top 1%
  into one 1%-wide bin at their population-weighted mean, BEFORE the PIP-side
  chain is rebuilt, so every series it returns is on a plain percentile grid
  (`DECK_BINS = 100`, `aggregate_to_percentiles()`). `etl_mld.decompose`
  defaults to 100.
  What it cost: at most **0.3pp** on any between share (PIP cons->income
  58.1 -> 58.4%), within down by <=0.003, and the between components identical —
  aggregation preserves each country's total income and population, so means and
  top-1% shares cannot move. Country Ginis from bins drop ~0.03, but the deck's
  Ginis are the sources' published ones.
  The raw `es.load()` still returns 109 bins, so
  `24_fig_top_of_distribution_from_etl.py` keeps its top-0.1% threshold row
  (slide 95, the 60-min section). That split — raw loader keeps the ETL's
  resolution, `load_bins` applies the deck's convention — is the thing to
  preserve if this is revisited.
  **Select by rank window, never by bin label.** `lollipop_records` was reading
  `by_pct["p90p91"]`, which assumes the grid AND that the label describes the
  rank — false for a re-ranked series (append re-reads every rank as 0.99x). It
  now integrates the window via `rank_window()`. Measured error from the old
  approach under append: 0.5% at P10 but **4.4-6.1% at P90**, because the
  displacement grows with rank (0.01 x p) while the income gradient is ~5% per
  percentile point at both.
  Also deleted: `slide-topadj-slopes-ex` (the chain explainer with the slope
  toggle) — Joe found it more confusing than helpful once the adjustment was
  simplified. `fig-topadj-explainer` is now used only in `mode: 'consinc'`, on
  `slide-consinc-slopes-ex`; its 'chain' mode still works but nothing uses it.
- **DONE 2026-09-09 — the graft and the anchor dimension are GONE; the top
  adjustment is the top 1%, two ways.** Joe's call. What replaced them, in
  `topadj.build_top1(bins, method)`: **match** (under-reporting — PIP samples the
  right people, its top 1% just reports too little, so that top 1% is rescaled
  until its income share equals WID's) and **append** (under-representation —
  the very rich are missing from the sample, so the WHOLE survey is re-read as
  the bottom 99% and WID's top percentile is added; Anand & Segal 2015, Handbook
  of Income Distribution 2A ch. 11, p. 954). Both aggregate the top 1% on both
  sides, so they differ in exactly one thing: the retained income `A` in the
  shared closed form `Y' = A/(1-S)` — `Y_s(1-s_P)` for match, `0.99 Y_s` for
  append. Both carry a **gate**: no country is adjusted whose own top-1% share
  already exceeds WID's, because "assume WID is right" would there mean revising
  its top DOWN. 4-5 countries are skipped (Cyprus, Denmark, Iceland,
  Switzerland, Tajikistan). With the gate, every adjusted country is monotone.
  The eight scenarios (2 methods x 4 bases: raw PIP, then the income basis at
  b = 0.10/0.12/0.14) span a between share of **46.8% to 58.7%**, all of them
  between PIP as published (69.2%) and WID post-tax per capita (38.7%). Append's
  mean uplift is 1.160 on every base — it depends on WID alone — while match's
  falls from 1.093 to 1.060 as b rises, because a steeper slope has already
  lifted PIP's top.
  **The deck baseline is a PLACEHOLDER.** `etl_source.TOPADJ_METHOD = "match"`,
  chosen because match is expressible on the 109-bin grid (its adjusted top is
  written back as the base's own ten 0.1% bins, all at the matched value — the
  same distribution, and every figure downstream keeps working) and append is
  not: append re-ranks everything by 0.99, so it lands on ranks the grid does not
  have. Making append the baseline needs a re-binning step that does not exist.
  Joe has not chosen on the merits.
  Torn out: `topadj.build_from_bins` / `build_share_matched_from_bins`,
  `etl_source.TOPADJ_SPLICE_PERCENTILE`, `30_fig_topadj_sensitivity.py` and
  `32_fig_consinc_topadj_cross.py` with their components, figures and slides.
  `build_pip_topadj` and `anchor_bin_label` SURVIVE in topadj.py — scripts 10-14
  and scenarios.py, the preserved reference implementation, still import them,
  and nothing the deck displays goes through them.
  Left alone deliberately: **Joe's own body text** on the slides still describes
  grafting and anchors. He asked to fix that himself.
- **DONE 2026-09-09 — the chain explainer now carries the whole cross, and its
  controls are radio groups.** `fig_topadj_explainer.json` was one income basis
  and six top-adjustment tails per country; it is now `consinc[beta]` and
  `variants[beta][splice][method]` — WID's three slopes x three anchors x two
  methods, each rebuilt end to end (359 KB -> 724 KB; income countries omit
  `consinc` entirely, because for them the income basis IS the PIP series at
  every slope, and the component falls back to `pip`). The script asserts the
  baseline slope reproduces the deck's own `PIP_consinc`.
  `fig-topadj-explainer` gained `mode` ('chain' | 'consinc'), `betas` and
  `splices` props, and BOTH its dropdowns became radio groups (Joe's call: three
  options each, so the whole choice set should be visible and one click away).
  Two new slides: `slide-consinc-slopes-ex` (mode 'consinc' — one full-width
  panel, consumption against the income basis at all three slopes, no top
  adjustment, country selector only) and `slide-topadj-slopes-ex` (both radio
  groups live, so the 3x6 cross is walkable one country at a time). The older
  explainer slides pass no `betas`, so they stay on the baseline slope with only
  the anchor control — the JSON shape changed under them but the component
  handles both.
  The three slopes are drawn as a light-to-dark ramp of the income-basis hue
  PLUS a dash pattern each (fine dots = flattest, long dashes = steepest): a
  redundant channel, since a single-hue lightness ramp of three dashed lines
  that nearly coincide in the middle of the distribution is hard to read
  otherwise. Not a categorical palette, so no validate_palette run.
- **DONE 2026-09-09 — the consumption->income slope is a RANGE, and it is now
  crossed with the top adjustment.** WID publish three values for the scaled
  logit's slope, b = 0.10 / 0.12 / 0.14 (`consinc.WID_PROFILE_B_SCENARIOS`, the
  middle one the deck's baseline and asserted to be a member). b carries the
  whole shape of the correction — a factors out as a level — so those three are
  the honest uncertainty in that step. Because the top adjustment is built ON the
  income-basis series (the graft scales WID's shape from the income-basis anchor
  value; share matching solves `Y' = A/(1-S)` from income-basis income below the
  anchor), the two choices COMPOUND, so the sensible object is the 3 x 6 cross,
  not two separate sensitivities. New: `32_fig_consinc_topadj_cross.py`,
  `components/fig-consinc-topadj-cross.js` and the cross slide
  (`slide-consinc-topadj-cross`) — rows are the seven top-adjustment options,
  column groups are the three slopes, cells are within / between / between share.
  The three slopes are ALSO drawn as split bars: `21_fig_bridging_from_etl.py`
  now emits TWO variant sets into one `variants` dict keyed by series — the six
  top-adjustment variants (on `PIP_topadj` / `WID_posttax_rescaled`) and the
  three slopes (on `PIP_consinc`, keyed i/ii/iii so the keys never clash with the
  top adjustment's a-f one slide away), each computed at the other choice's
  baseline.
  `fig-raw-comparison`'s `variants` prop therefore takes an ARRAY of series
  names, not just `true`, so `slide-consinc-variants` splits the income-basis
  column with the top-adjusted column blanked (`dimOpacity: 0`) and
  `slide-topadj-variants` does the reverse. `true` still means "every series with
  a block", which is now the wrong thing on either of those slides — name the set.
  Each variants block carries its own `caption` for the a/b/c key line, so no
  English about which choice is being varied lives in the component.
  The script asserts the baseline cell reproduces the deck's own `PIP_consinc`,
  `PIP_topadj` AND `WID_posttax_rescaled` exactly.
  Findings: the slope moves the between share ~2pp per step (57.6 / 55.5 / 53.3%
  at the baseline top adjustment); the top-adjustment choice moves it ~6pp at a
  fixed slope. Across all 18 cells: between share 46.4-58.0%, within 0.360-0.523
  — versus PIP as published 69.2% / 0.214 and WID post-tax 38.7% / 0.615. Both
  directions are monotone: steeper b or a more generous top method means more
  within-country inequality and a lower between share. **Trap worth remembering:**
  `etl_mld.floor_for()` recognises the deck's WID series BY NAME, so a rescaled
  WID series built under a scratch series name silently falls back to the ETL's
  $0.01 zero convention and lands ~5pp off. Pass `floor_rule` explicitly for
  scratch names — the cross script's `cell()` documents this.
- **DONE 2026-09-09 — the deck's baseline top adjustment moved from the graft at
  P95 to the graft at P98** (Joe's call). One line does it:
  `etl_source.TOPADJ_SPLICE_PERCENTILE`, which `load_bins()` uses to rebuild the
  whole PIP-side chain, so `PIP_topadj` and `WID_posttax_rescaled` move together
  everywhere — the global decomposition, the three-country (US / Indonesia /
  Nigeria) lollipops and bars, the explainer's default, the sensitivity table's
  marker, and the top-1% scatter's default series. `21`, `23`, `29`, `30` and
  `31` now READ that constant instead of restating it; `23`'s anchor-bin
  assertion was pinned to bin index 94 and had to be derived instead.
  What changed: global within-country MLD 0.417 -> 0.394, total 0.910 -> 0.886,
  between share 54.2% -> 55.5%; the median country's top-1% multiplier 1.79 ->
  1.45 and its top-1% share 12.5% -> 11.0% (WID 14.6%); grafted P99 thresholds
  fall about 9-14% (US $13,810 -> $12,370/month). `WID_posttax_rescaled` barely
  moves (between share 44.5% -> 44.4%) because its within component is
  untouched by definition. PIP and PIP_consinc are unchanged.
  Why it moves that way: PIP sits further below WID the higher up you look, so a
  later anchor gives a smaller scale factor — P98 is the more CONSERVATIVE
  allowance for the missing top. Which means the slide kicker "guesstimated
  upper bound" is now a weaker claim than it was: the baseline is fourth of the
  six variants, and share matching at P95 (within 0.500, between share 47.7%) is
  the actual upper bound. Two figures still carry the OLD baseline and the ETL's
  own PIP_topadj because they read `es.load()` rather than `es.load_bins()`:
  `fig_top_thresholds` (slide 89, the 60-min deck) and `fig_between_share_trend`
  (which is also still on the old zero convention, and says so on its slide).
- **DONE 2026-09-09 — the top adjustment is a 2x3 cross, and the choice is now
  drawn.** Two methods x three anchors: the **graft** imports WID's post-tax
  *shape* above the anchor and lets the resulting top share follow
  (`topadj.build_from_bins`); **share matching** imports WID's ten top-1%
  *sub-shares* exactly and lets the shape follow
  (`topadj.build_share_matched_from_bins`, closed form `Y' = A/(1-S)`). Anchors
  P95 / P98 / P99. Both are uniform rescalings of WID's top, differing only in
  the scale factor — which is why India moves a lot (PIP is 25% of WID on
  average but only 14% at P98) and the UK barely does. Three deck surfaces:
  `fig-topadj-explainer` gained an anchor toggle and draws both methods;
  `fig-topadj-sensitivity` (slide 27) tabulates the cross; and slide 28
  (`slide-topadj-variants`) draws all six onto the global bars via
  `fig-raw-comparison`'s new `variants: true` prop — one thin stacked bar per
  variant inside the same column footprint, so only the column that moves (PIP
  top-adjusted) has any width. WID post-tax rescaled moves with the choice too,
  since its country means are forced onto PIP top-adjusted, and the JSON carries
  its variants; Joe dropped that column from this slide (2026-09-09), so it
  splits only if a `sources` prop puts it back. The labelled ranges are **synthetic envelopes**: each
  component's and each share's min and max taken separately, so the endpoints
  need not come from one variant (`within` bottoms out at the P99 graft while
  `between` tops out at the P95 graft). Joe's call, and the chart says so. The
  whole spread of the between share for PIP top-adjusted is 48-56% — narrower
  than the gap that remains to the WID side, which is the point of showing it.
  The abandoned branch: WID's own survey->fiscal (Lomax) correction was built
  and then removed at Joe's request; don't rebuild it.
- **DONE 2026-09-09 — consumption->income switched to WID's correction profile.**
  Chasing a kink at the top of the explainer chart led to the real problem: the
  per-percentile log-log regression made the correction depend on the income
  LEVEL, and its coefficients existed only at percentile resolution, so the ten
  0.1% bins above P99 borrowed the p=100 pair — flattening inequality inside the
  top percentile. Replaced with WID's scaled logit,
  `Q_I(p)/Q_C(p) = 0.85 + 0.12*log(p/(1-p))` (Chancel, Cogneau, Gethin &
  Myczkowski 2019, WID.world WP 2019/13), using **WID's parameters**, because
  PIP's 88 dual country-years are not a usable estimation sample: 73 of them
  compare two DIFFERENT surveys (budget survey vs EU-SILC — verified against
  PIP's API `survey_acronym`), giving income above consumption at every rank and
  a crossover at ~P12 instead of ~P79. The 15 same-instrument pairs fix the fit
  (R2 0.42 -> 0.90) but not the level, because 9 of them are the Philippines.
  None of the 88 are from Sub-Saharan Africa or South Asia, where it is applied.
  2023 between-country shares: PIP_consinc 60.0% -> 58.1%, PIP_topadj
  55.2% -> 54.2%, WID_posttax_rescaled 41.8% -> 44.5%. PIP itself unchanged.
  **The whole PIP-side chain is now rebuilt in this repo** (`etl_source.load_bins`
  -> consinc -> topadj -> rescale), because each step feeds the next; leaving the
  ETL's PIP_topadj would pair a rebuilt base with a graft anchored to the old one.
  Guards assert income countries pass through untouched and consumption countries
  match the profile exactly.
  This also SUPERSEDED the top-1%-aggregation fix made earlier the same day — the
  profile is continuous in rank, so it needs no special handling above P99.
  **The reference implementation is now out of step:** `04_fit_consinc.py` and
  `13_fig_consinc_explainer.py` still implement the regression, and
  `consumption_income_model` in the ETL cache is no longer read by any deck figure.
  **Open:** whether to raise the method change with the ETL team, as with the
  zero-income floor.
- **DONE 2026-09-08 — the zero-income floor: WID now bottom-coded at 1% of
  country mean.** Found while checking two oddities on the country-level MLD
  scatter: an apparent floor of ~0.7 on WID within-MLD, and the US ranking 37th
  of 44 on within-MLD against 12th on WID's own Gini. Both had one cause — WID
  pre-tax reports exactly zero for the bottom ~5 percentiles in 184 of 211
  countries (DINA allocates zero rather than dropping people), and at the ETL's
  $0.01/day replacement those bins supplied a **median 43.5%** of each country's
  within-MLD. The US is one of only 26 countries with NO zero bins, so it was
  the only one being measured honestly.
  Now: WID series bottom-coded at 1% of each country's raw mean (LIS practice);
  PIP left exactly as the World Bank publishes it (already bottom-coded at
  $0.28/day, no zero bins). Rule defined once in `mld.py:country_floor()`,
  applied on the ETL path by the new `etl_mld.py`.
  Effects, 2023: WID pre-tax per capita within 1.000 -> 0.801, between share
  28.0% -> 32.7%; per-adult 21.1% -> 25.5%. Post-tax moves ~0.2pp, PIP not at
  all. US rank 37th -> 13th (Gini rank 12th); correlation with WID's Gini
  0.81 -> 0.94; the 0.7 floor is gone (min within-MLD 0.433).
  **The decompositions are now computed in this repo** (`etl_mld.py`) rather
  than read from the ETL's ready-made tables — a deliberate step back from the
  "computed once" principle in `etl_source.py`, taken because the ETL's floor
  is not defensible for WID. `etl_mld.main()` is the regression test: with the
  ETL's own convention the recompute reproduces its published numbers to 6e-08.
  **Raise upstream with the ETL team** — the floor belongs there, not here.
  **Known gap:** `fig_between_share_trend` (slide 103) still uses the old
  convention and says so on the slide; it needs all 35 years of bins and only
  the display year is cached, because the deck's WID vintage lives only in
  owid/etl#6806's staging output, not the public catalog (verified: the catalog
  copy differs from the cache for 95-99% of WID rows).
  Also dropped the `mld_by_year` / `lollipop_by_year` blocks from four figure
  JSONs — no component ever read them (`fig_raw_comparison.json` 298 KB -> 11 KB,
  `fig_bridging_all.json` 73 KB -> 5 KB).
- **DONE 2026-09-08 — price-basis audit and documentation fix.** Established
  what the two sources' monetary values actually are, and corrected five wrong
  statements in the docs. The headline: **both sources use the 2021 PPP round;
  only the PRICE BASE differs** (PIP 2021 prices, WID 2025 prices). The old
  claim that they came from "different PPP rounds/vintages"
  (`data/README.md`, `02_process_wid.py`) was wrong — WID's `xlcusp`
  re-expressed at a 2021 base reproduces the World Bank's published 2021 PPPs
  (`PA.NUS.PPP`) for 184 of 197 countries to within 0.01%; the six outside 1%
  are currency-unit artefacts (Bulgaria = the BGN/EUR peg exactly, Zimbabwe a
  redenomination). Also confirmed the ETL path arrives in **2021-PPP int-$ at
  2025 prices** (ETL cache 71,410.28/yr vs 71,410.40/yr computed independently
  for US 2023), so the local pipeline and the ETL agree.
  **DECIDED 2026-09-08: the deck stays on 2025-price WID — not re-basing.**
  Re-basing to 2021 prices was investigated and would have been a single scalar
  (x0.854244 = WID's US national income price index for 2021, `inyixx999i`),
  because the country's own inflation cancels against `xlcusp`; verified end to
  end against directly-fetched WID data to 9e-06 % across 215 countries. It
  moves no inequality result (uniform rescale), drops WID dollar labels 14.6%,
  and changes exactly one message — the means scatter's survey share of national
  income, 39.5% -> 46.3% (2023). Not adopted: the proper home for such a fix is
  OWID's ETL rather than a scalar in this repo, which would put the deck's
  numbers out of step with the ETL's. No code applies it and no constant is
  left behind; the reasoning is kept in `data/README.md` §"Prices, PPPs and the
  two price bases" so it is not re-derived from scratch.
  **The live consequence to remember:** cross-source LEVEL comparisons (the
  means scatter) inherit a four-year price gap — WID sits ~17% higher than a
  like-for-like comparison would put it. Relative measures are unaffected.
  Also established: `inyixx999i` is mostly the World Bank GDP deflator (closer
  than CPI for 143 of 168 countries) — there is no WID-specific "national
  income deflator", as earlier notes implied.
- **DONE 2026-08-27, committed 2026-09-02 — the PPP price-base fix.** WID
  publishes incomes in constant LCU of the *latest database year*, so converting
  them with `xlcusp(2023)` overstated every country by its inflation relative to
  the US over 2023–25 — ~4x for Venezuela, Sudan and Argentina, ~2x for Turkey.
  `config.PPP_YEAR = 2025` now drives the conversion; both processed CSVs and all
  figure JSONs were regenerated and `99_verify.py` passes 19/19. See §12.
- **DONE 2026-08-27 — the survey-vs-national-accounts figure**
  (`fig-means-scatter.js`, slides 19/20/22), the project's first two-year figure.
  Originally `17_fig_means_scatter.py` off the local pipeline.
- **DONE 2026-09-02 — that figure is now ETL-sourced** (`28_fig_means_from_etl.py`),
  the last chart to move over. It was left behind by Pablo's port, which meant it
  sat on the OLD data vintage while its own slide neighbours sat on the new one,
  and `refresh_from_etl.py` did not touch it. Numbers moved: WID means −3.0%
  (1990) / −4.5% (2023) at the median, concentrated in high-inflation and
  conflict economies (Syria +102%, Yemen +88%, Venezuela −71%, Sudan −44%); PIP
  means unchanged at the median. **The median WID/PIP ratio fell 2.55x → 2.33x
  in 2023.** Regions come from the ETL's `treemap_regions`, verified to
  reproduce the local 8-region scheme exactly (218 countries, 0 disagreements).
- **CLOSED 2026-09-02 by that port — the two reproducibility gaps are moot.**
  The missing `18_fetch_wid_means.py` and the single-year `01_fetch_pip.py` only
  mattered because figure 17 read `WID_national_income_means.csv` and
  `pip_thousand_bins_1990.csv.gz`. Nothing the deck renders reads either file
  now. Both inputs (and `17_`) are kept as the reference implementation; don't
  write the missing fetch script.
- **DONE 2026-09-02 — the superseded figure scripts are guarded.** `10`–`17`
  share output filenames with the ETL scripts, so running one silently replaced
  whole-panel ETL figures with 2023-only local ones (WID between share moves
  3–4pp). They now exit 2 unless given `--write-legacy-figures`
  (`data/scripts/legacy_guard.py`), and `data/README.md`'s old figure-scripts
  section carries a warning instead of the stale "re-run the figure scripts"
  instruction.
- **OPEN — ask Pablo why the WID numbers moved.** Porting the Q2 figures changed
  the WID between-country share by 3–4pp (e.g. pre-tax per adult 26.2% → 29.4%,
  same year, same zero handling, same splice) and the WID country means by the
  amounts above. Not the population yardstick (documented as ≤0.02pp). Presumably
  a newer WID vintage or a different PPP vintage — the movers are the countries
  where PPP conversion is fragile — but it is not written down anywhere, and
  these are numbers Joe says out loud in the talk.
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
  processed/            # regenerable outputs incl. pip_wid_harmonized_2023.csv (local
                        # pipeline) and reference_year_indicators.csv (ETL-derived, 33_)
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
