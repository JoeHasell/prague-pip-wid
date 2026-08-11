# PROJECT NOTES — "prague-pip-wid" deck

> Handoff notes for a future chat. Read this first, then `README.md` for the
> framework mechanics. Last updated: 2026-08-10.

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

The project files live on **Joe's Mac**, in a connected folder:

```
/Users/joehasell/Documents/Claude/Projects/prague-pip-wid
```

The assistant runs in a **cloud sandbox** and reaches those files through the
`mcp__remote-devices__*` bridge. The reliable loop is:

1. **Read**: `device_stage_files` the file(s) → they appear under
   `/mnt/user-data/uploads/...` (read-only). Copy to `/tmp` to modify.
2. **Edit / build / verify** in the sandbox.
3. **Deliver**: `SendUserFile` (gives a `file_uuid`) → `device_commit_files`
   with that uuid and the device path.
4. **Guard writes**: pass `expectedMtimeMs` (from the stage result) on
   `device_commit_files`. If it's **rejected** ("device file changed since
   stage"), the user saved in the browser meanwhile — **re-stage, re-apply your
   change onto their latest, commit again.** Never `force` over their edits.

**The two-writer caveat (this bit really matters):** Joe edits `slides.json` live
in the browser while the assistant also writes it. Whoever saves last wins, and a
stale browser tab can silently roll back the assistant's most recent change (this
has happened). Habits that avoid it:
- **Always re-stage `slides.json` immediately before editing it.**
- Tell Joe to **reload the browser after you write**, and to **Save before**
  handing you a task.
- `src/*` and `components/*` are only ever edited by the assistant (the browser
  editor touches `slides.json` only), so those rarely collide — but still stage
  fresh before editing.

**The dev server is user-side only.** `node dev-server.js` runs on Joe's Mac at
`http://localhost:4173` (`/?edit` to author). The cloud sandbox **cannot reach
that localhost** — do all rendering/verification with the headless harness (§9).

**Note on `src/` changes:** editing `src/deck.js`, `src/editor.js`, CSS requires
Joe to **restart the dev server + hard-refresh**. `slides.json`-only changes need
just a reload.

## 4. Current state of the deck (as of this handoff)

17 slides. **Slides 1–9 are the real talk-in-progress; slides 10–17 are the
original template demo slides** (leftover; safe to delete when Joe says so — they
also carry the demo components).

| # | id | what it is |
|---|----|-----------|
| 1 | slide-title | Title. "What do we know about global income inequality?" |
| 2 | slide-rmm9en | Overview (bulleted, incl. nested bullets) |
| 3 | slide-52qg9a | "Three basic questions" — a **table** (`class="deck-table small"`) comparing PIP / WID "headlines" / Triangulated across Q1–Q3 + income concept, data sources, measure, strengths, weaknesses |
| 4 | slide-scatter-gw | **Scatter**: PIP Gini (x) vs WID **pre-tax** Gini (y), ~2019, colour by WB region, 45° line. `gini-pip-wid-scatter` props `{}` |
| 5 | slide-scatter-gw-post | Same scatter, WID **post-tax** national income. props `{measure:"posttax"}`. Flick 4↔5 to see the cloud drop toward the diagonal |
| 6 | slide-scatter-gw-reg | Post-tax scatter with **register-based-income countries highlighted**, others faded. props `{measure:"posttax", highlightGroup:"register"}`. (has 1 annotation) |
| 7 | slide-riurji | **Two-panel** 1993-vs-2019 scatter (PIP left, WID right), 45°=no change; metric radio Gini/Top10%/Palma/**Top1%**. `ineq-trend-scatter` props `{metrics:["gini","top10","palma","top1"]}` |
| 8 | slide-qs05wh | **Change-vs-change** scatter: Δ PIP (x) vs Δ WID (y); radios for metric and absolute/relative. `ineq-change-scatter` props `{}` |
| 9 | slide-2bc0nk | A **hand-drawn sketch** slide (24 pen/line/text annotations) Joe made with the draw tool |
| 10–17 | slide-cl7jpk, slide-model, slide-chart, slide-1kotk6, slide-table, slide-row, slide-editing, slide-publish | **Original template demo slides** — placeholder, remove when ready |

`meta.title` is still the template default ("Deck framework — demo") — editorial
TODO to rename.

## 5. Components built

Registered in `components/manifest.json`:
`gini-pip-wid-scatter.js`, `ineq-trend.js`, plus the three `demo-*.js`.

### `gini-pip-wid-scatter` (file: `gini-pip-wid-scatter.js`)
One dot per country, PIP Gini (x) vs WID Gini (y), ~2019 reference year, colour by
**World Bank PIP region** (Okabe-Ito colourblind-safe palette), 45° "sources
agree" line, hover tooltips. **58 countries** embedded in the file as
`[{c, p (pip gini), wPre (wid pretax), wPost (wid posttax), r (region), y (year)}]`.
Props (all optional):
- `measure`: `"pretax"` (default) or `"posttax"` — which WID series on Y. Axes are
  identical for both so slides 4/5 flick cleanly.
- `highlight`: array of country names to keep in colour (others faded); or
  `highlightGroup:"register"` for the built-in register list.
- `title`, `yLabel`, `source`, `min`, `max` (axis domain, default 0.2–0.8), `data`.

### `ineq-trend.js` — registers TWO components (shares one embedded dataset)
Embedded data: **115 countries**, `[{c, r (WB region), <metric>_<pip|wid><93|19>}]`
where metric ∈ {`gini`, `top10`, `palma`, `top1`}. Note **`top1` (top-1% share)
exists for WID only** (all `top1_pip*` are null) — PIP has no top-1% series.
- **`ineq-trend-scatter`** (slide 7): two panels (PIP left, WID right), each a
  scatter of a country's inequality in **1993 (x) vs 2019 (y)**; 45°=no change.
  Prop `metrics` (default `["gini","top10","palma"]`; slide 7 adds `"top1"`),
  `metric` (default first). Uses **max coverage per source** (97 PIP / 90 WID for
  Gini/Top10/Palma; 0 PIP / 90 WID for Top1 → PIP panel intentionally blank).
- **`ineq-change-scatter`** (slide 8): one scatter, **Δ PIP (x) vs Δ WID (y)** with
  zero quadrant lines + 45° agreement line. Props `metrics`, `metric`, `mode`
  (`"abs"` default | `"rel"`). Uses the **72-country intersection** (both sources,
  both years). `abs` = 2019−1993 in metric units; `rel` = (2019−1993)/1993 ×100%.

### CSS conventions (in `src/deck.css`)
- Tables in text blocks: `<table class="deck-table">` (add `small` for compact
  font) → OWID-styled, and stay click-to-edit in `?edit`.

## 6. Data provenance (so a future chat can reproduce / extend)

All data is from **Our World in Data** via the `owid-catalog` Python library
(`pip install owid-catalog --break-system-packages`; `from owid.catalog import
fetch, search`).

**Primary comparison dataset** (basis of slides 4–8):
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
- Slides 4–6 use the **~2019** point where both sources exist → **58 countries**.

**Post-tax WID** (slide 5/6 `posttax`): the comparison dataset only has pre-tax
WID, so post-tax comes from the main WID dataset:
```
grapher/wid/2026-06-18/world_inequality_database/inequality
  gini__welfare_type_before_tax__extrapolated_yes   # = pre-tax national income; reproduces the comparison pre-tax values EXACTLY at the same country-years (verified)
  gini__welfare_type_after_tax__extrapolated_yes    # = POST-TAX national income (used for `posttax`)
  gini__welfare_type_after_tax_disposable__...       # alt: post-tax DISPOSABLE income (not yet used; offered as a future option)
```
So slides 4→5 differ *only* in tax treatment (national income, per adult, same
countries/years). Post-tax narrows the mean WID−PIP gap from ≈0.18 to ≈0.12.

**Regions:** World Bank PIP `region_name` from
`grapher/wb/2025-04-14/world_bank_pip/world_bank_pip#region_name__poverty_line_no_poverty_line__welfare_type_income_or_consumption__table_income_or_consumption_consolidated__survey_comparability_no_spells`
(7 groups incl. the non-geographic "Other high income countries"). An alternative
continent mapping is `continents-according-to-our-world-in-data` (`owid_region`).

**Units:** Gini 0–1; top-10% / top-1% shares in %; Palma is a ratio (~0.8–3+).

**Where the data currently lives:** embedded directly inside the component JS
files (no runtime fetch). If a metric/coverage/source changes, re-run the
extraction and regenerate the embedded arrays. (The extraction scripts were run
in the sandbox and not committed — ask Joe if he wants them saved into a
`data/` folder for reproducibility; recommended for the next data-heavy phase.)

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
(slide 9's sketch pushed the file to ~200 KB — normal, just noticeable).

## 9. Environment & verification recipes (sandbox)

- **owid-catalog**: `pip install owid-catalog --break-system-packages`.
- **Headless render harness** (to *see* a slide, since localhost is unreachable):
  serve the project and screenshot with the preinstalled Chromium.
  ```bash
  cd <project>; python3 -m http.server 8300 &
  # playwright: chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
  # page.goto('http://localhost:8300/#<N>'), screenshot; add ?edit to test tools.
  ```
  Read the PNG back to eyeball layout/colours. Use `page.evaluate` to poke
  `Deck.data` / dispatch events to test interactivity (radios, draw tools).
- **Palette validator**: dataviz skill →
  `node scripts/validate_palette.js "<hex,hex,...>" --mode light --pairs all`.
- Always `node --check` edited JS and `JSON.parse` edited JSON before delivering.

## 10. Open threads / next steps

- **IN PROGRESS: Q2 (between- vs within-country decomposition).** The data
  foundation is built — see §12. Joe's prior research project
  (`~/Documents/GitHub/data_work/global_inequality_pip_wid`) was "re-potted":
  its WID fetch + harmonization pipeline now lives in `data/`, verified
  end-to-end. **Analyses and figures are being built FRESH against
  `data/processed/pip_wid_harmonized_2023.csv`** — the old project's analysis
  scripts/charts were deliberately not migrated (treat them as reference
  only; several of its README headline numbers predate a critical PPP bug
  fix and are stale). New chart components must fetch their data from
  per-figure files produced by pipeline scripts — no more hard-coded data
  arrays in component JS.
- Editorial TODOs (Joe's call, don't do unprompted): rename `meta.title`; give
  slides 7 & 8 distinct headings (both currently under the Q1 kicker); slide 3
  table Q3 row still has `??` cells; decide fate of demo slides 10–17 and the
  `demo-*` components.
- Offered-but-not-built: post-tax **disposable** WID variant (vs national income)
  on slides 5/6; per-region marker shapes for stronger CVD separation; an
  "add row / add column" control for `deck-table` in the editor.

## 11. File map

```
content/slides.json     # all slide content + per-slide annotations (SINGLE SOURCE OF TRUTH)
components/
  manifest.json         # list of component files to load
  gini-pip-wid-scatter.js   # slides 4–6 scatter (pre/post-tax, region highlight)
  ineq-trend.js             # slides 7–8 (trend + change scatters; two components)
  demo-*.js                 # template demos (used only by demo slides 12/14/15)
data/                   # REPRODUCIBLE DATA PIPELINE (see §12 and data/README.md)
  scripts/              # numbered pipeline steps + verification suite
  raw/                  # committed raw caches (WID API pull, PIP extract)
  processed/            # regenerable outputs incl. pip_wid_harmonized_2023.csv
src/
  deck.js               # engine: render, nav, components, ANNOTATION overlay
  deck.css              # theme + .deck-table + .slide-annot styles
  editor.js             # ?edit editor: text, lists, component props, DRAW tools
  editor.css            # editor chrome + draw palette/tool styles
index.html, dev-server.js, netlify.toml, README.md
PROJECT_NOTES.md        # this file
```

## 12. The data pipeline (added 2026-08-10)

`data/` holds the reproducible pipeline for the Q2 phase (between- vs
within-country inequality), re-potted from Joe's prior research project.
**Read `data/README.md` first** — it documents the five series, the income
concepts, and six known caveats. Key facts for a fresh session:

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
- **Always run `python data/scripts/99_verify.py` after touching the
  pipeline** (19 checks; encodes two historical bugs: missing PPP conversion,
  wrong bin population weights).
- **MLD weighting convention:** ALL MLD decompositions weight countries by
  WID's demography, MATCHED TO THE SERIES' BASIS (adults for per-adult
  series, total population otherwise — incl. for PIP) — via the single
  shared module `data/scripts/mld.py`. Never compute an MLD decomposition
  without it (per-source population weights leak WID-vs-PIP demographic
  disagreements into the between component; decided 2026-08-11).
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
