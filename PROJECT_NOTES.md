# PROJECT NOTES — "prague-pip-wid" deck

> Handoff notes for a future session. Read [`CLAUDE.md`](CLAUDE.md) first (how to
> work in this repo), then this file, then `README.md` for the framework mechanics
> and `data/README.md` for the pipeline. Last updated: 2026-09-02 (migrated from
> Claude Cowork to Claude Code).

## ⚠️ Refreshing the data after an ETL change

The figures are committed JSON built from a cached ETL extract; nothing in this repo
watches the ETL. After any ETL change, and before presenting, run:

```bash
# while owid/etl#6764 is open — the datasets live only on staging:
python data/scripts/refresh_from_etl.py --staging worktree-etl-prague-pip-wid

# once #6764 merges, drop the flag to read the public catalog:
python data/scripts/refresh_from_etl.py
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

**This project moved from Claude Cowork to Claude Code on 2026-09-02, and works
LOCAL-FIRST.** The Cowork-era protocol (the `mcp__remote-devices__*` file bridge,
staging into `/mnt/user-data/uploads`, `device_commit_files` with
`expectedMtimeMs`, and the hard rule "the assistant must never run git") is
**obsolete**. [`CLAUDE.md`](CLAUDE.md) holds the current rules; the essentials:

- **Default to a LOCAL session** — in the desktop app's **Code** tab, Environment
  = **Local**, project folder `~/Documents/Claude/Projects/prague-pip-wid`. Claude
  then reads and writes Joe's actual working copy, exactly as Cowork did, and can
  run `git`. Joe never touches the command line: **Claude does the git work**,
  including committing Joe's own browser edits ("I made changes in the browser —
  push them" is a request Claude can simply carry out).
- **A CLOUD session is an isolated VM with a fresh clone and no access to Joe's
  Mac.** His browser edits are unreachable from there — he'd have to push them
  from GitHub Desktop first. Reserve cloud sessions for long autonomous jobs he
  wants running with the laptop shut. `$CLAUDE_CODE_REMOTE=true` marks one.
- **Stata is only on the Mac**, so `00_fetch_wid.py` can *only* run in a local
  session — the one pipeline step a cloud session can never do.
- **The two-writer trap that survives both:** the `?edit` editor holds the whole
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

## 4. Current state of the deck (as of this handoff)

**38 slides**, in four groups:

- **1–4 — a short (15 min) cut** of the talk, drafted separately: title, OWID's
  role, "the two main sources give opposite answers", summary.
- **5–28 — the full (60 min) talk in progress**, organised Q1 → Q2 → Q3.
- **29–30 — literature review / reading list** (working notes).
- **31–38 — original template demo slides** ("How to edit", the three `demo-*`
  components). Leftover; safe to delete when Joe says so.

| # | id | what it is |
|---|----|-----------|
| 1 | slide-title-short | Short-cut title: "Where does global inequality lie: between or within countries?" [DRAFT] |
| 2 | slide-owid-role | Goals / role of Our World in Data |
| 3 | slide-two-sides | "The two main sources give opposite answers" |
| 4 | slide-short-summary | Summary of the short cut |
| 5 | slide-title-full | Full-talk title (60 min) [DRAFT] |
| 6 | slide-title | Earlier title slide (same heading; superseded by 5) |
| 7 | slide-rmm9en | Overview (bulleted, incl. nested bullets) |
| 8 | slide-52qg9a | "Three basic questions" — `deck-table small` comparing PIP / WID headlines / triangulated across Q1–Q3 + income concept, sources, measure, strengths, weaknesses |
| 9 | slide-scatter-gw | **Q1** scatter: PIP Gini (x) vs WID **pre-tax** Gini (y), ~2019, colour by WB region, 45° line. `gini-pip-wid-scatter {}` |
| 10 | slide-scatter-gw-post | Same scatter, WID **post-tax** national income — `{measure:"posttax"}`. Flick 9↔10 to see the cloud drop toward the diagonal |
| 11 | slide-scatter-gw-reg | Post-tax scatter, **register-income countries highlighted** — `{measure:"posttax", highlightGroup:"register"}`. (1 annotation) |
| 12 | slide-riurji | **Two-panel** 1993-vs-2019 scatter (PIP left, WID right), 45°=no change; metric radio. `ineq-trend-scatter {metrics:["gini","top10","palma","top1"]}` |
| 13 | slide-qs05wh | **Change-vs-change**: Δ PIP (x) vs Δ WID (y); metric + abs/rel radios. `ineq-change-scatter {}` |
| 14–16 | slide-2bc0nk, slide-ckgbyw, slide-m37q6c | **Hand-drawn sketch slides** (24 / 27 / 27 pen-line-text annotations) Joe made with the draw tool |
| 17 | slide-yp4gbg | **Q2** section opener: "Which is bigger — between or within countries?" (includes the two reference images in `content/images/`) |
| 18 | slide-q2rawcmp | Raw WID-vs-PIP comparison, 3 countries: P10/P90/mean lollipops + between/within MLD bars. `fig-raw-comparison {title:""}` |
| 19 | slide-q2mldex | Anatomy of the MLD decomposition. `fig-mld-decomp {}` |
| 20 | slide-q2bridge | Bridging steps, 3-country sample — `fig-raw-comparison` with an explicit `sources` list |
| 21 | slide-q2consinc | Consumption→income mapping explainer (per-country fits). `fig-consinc-explainer {}` |
| 22 | slide-q2topadjex | Top-adjusted PIP series explainer. `fig-topadj-explainer {}` |
| 23 | slide-q2bridgeall | Bridging steps over the **full 211-country sample** — `fig-raw-comparison {dataUrl:"data/figures/fig_bridging_all.json", ...}` (bars-only mode) |
| 24 | slide-r2fdmx | **Q3** section opener: "Who are the richest 1% in the world?" |
| 25 | slide-q3thresh | Entry income for the global top 10% / 1% / 0.1% across the seven scenarios. `fig-top-thresholds {title:""}` |
| 26 | slide-q3treepip | Treemap of the global top 1%, **PIP** — `fig-top1-treemap {source:"PIP"}` |
| 27 | slide-q3treewid | Same treemap, **WID post-tax per capita** — `{source:"WID_posttax_per_capita"}` |
| 28 | slide-ct1u0k | Q3 wrap-up text |
| 29–30 | slide-tjof1k, slide-3382ld | Literature review / reading list |
| 31–38 | slide-ers737, slide-model, slide-chart, slide-1kotk6, slide-table, slide-row, slide-editing, slide-publish | **Original template demo slides** — placeholder, remove when ready |

24 of the 38 slides carry speaker `notes` (the **N** key).

`meta.title` is still the template default ("Deck framework — demo") — editorial
TODO to rename.

## 5. Components built

Registered in `components/manifest.json`: `gini-pip-wid-scatter.js`,
`ineq-trend.js`, the six `fig-*.js` figure components, plus the three `demo-*.js`.

Two generations, and the difference matters:

- **`gini-pip-wid-scatter.js` and `ineq-trend.js` (Q1 slides) embed their data
  arrays in the JS.** Pre-date the pipeline. If their numbers ever need to change,
  the extraction has to be re-run by hand — the scripts were never committed.
- **The `fig-*.js` components (Q2/Q3 slides) fetch `data/figures/fig_*.json`**,
  each generated by a numbered script in `data/scripts/`. This is the convention
  for anything new: no hard-coded numbers in component JS. The per-figure table
  (script → figure → component) lives in `data/README.md`; don't duplicate it here.

### `gini-pip-wid-scatter` (file: `gini-pip-wid-scatter.js`)
One dot per country, PIP Gini (x) vs WID Gini (y), ~2019 reference year, colour by
**World Bank PIP region** (Okabe-Ito colourblind-safe palette), 45° "sources
agree" line, hover tooltips. **58 countries** embedded in the file as
`[{c, p (pip gini), wPre (wid pretax), wPost (wid posttax), r (region), y (year)}]`.
Props (all optional):
- `measure`: `"pretax"` (default) or `"posttax"` — which WID series on Y. Axes are
  identical for both so slides 9/10 flick cleanly.
- `highlight`: array of country names to keep in colour (others faded); or
  `highlightGroup:"register"` for the built-in register list.
- `title`, `yLabel`, `source`, `min`, `max` (axis domain, default 0.2–0.8), `data`.

### `ineq-trend.js` — registers TWO components (shares one embedded dataset)
Embedded data: **115 countries**, `[{c, r (WB region), <metric>_<pip|wid><93|19>}]`
where metric ∈ {`gini`, `top10`, `palma`, `top1`}. Note **`top1` (top-1% share)
exists for WID only** (all `top1_pip*` are null) — PIP has no top-1% series.
- **`ineq-trend-scatter`** (slide 12): two panels (PIP left, WID right), each a
  scatter of a country's inequality in **1993 (x) vs 2019 (y)**; 45°=no change.
  Prop `metrics` (default `["gini","top10","palma"]`; slide 12 adds `"top1"`),
  `metric` (default first). Uses **max coverage per source** (97 PIP / 90 WID for
  Gini/Top10/Palma; 0 PIP / 90 WID for Top1 → PIP panel intentionally blank).
- **`ineq-change-scatter`** (slide 13): one scatter, **Δ PIP (x) vs Δ WID (y)** with
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

**Primary comparison dataset** (basis of the Q1 slides, 9–13):
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
- Slides 9–11 use the **~2019** point where both sources exist → **58 countries**.

**Post-tax WID** (slides 10/11, `posttax`): the comparison dataset only has pre-tax
WID, so post-tax comes from the main WID dataset:
```
grapher/wid/2026-06-18/world_inequality_database/inequality
  gini__welfare_type_before_tax__extrapolated_yes   # = pre-tax national income; reproduces the comparison pre-tax values EXACTLY at the same country-years (verified)
  gini__welfare_type_after_tax__extrapolated_yes    # = POST-TAX national income (used for `posttax`)
  gini__welfare_type_after_tax_disposable__...       # alt: post-tax DISPOSABLE income (not yet used; offered as a future option)
```
So slides 9→10 differ *only* in tax treatment (national income, per adult, same
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
(the sketch slides pushed the file past 500 KB — normal, just noticeable).

## 9. Environment & verification recipes

Full environment tables in `CLAUDE.md`. The recipes below work in both a local
and a cloud session; the differences are called out.

- **Local session (Joe's Mac):** the Python and Node are his, not a clean
  container — check before assuming a package is present, and prefer
  `pip install -r data/requirements.txt` over ad-hoc installs. The SessionStart
  hook deliberately does **not** run here. **Stata lives here**, so this is the
  only place `00_fetch_wid.py` can run (still ~1–2 h; don't run it casually).
  If `:4173` already answers, that's Joe's dev server — use it, don't kill it.
- **Cloud session:** a **SessionStart hook does the setup**
  (`.claude/hooks/session-start.sh`, registered in `.claude/settings.json`,
  guarded on `$CLAUDE_CODE_REMOTE`). It installs pandas + pyarrow from
  `data/requirements.txt` and playwright into `~/.deck-tools` — outside the repo,
  reachable via the `$NODE_PATH` it exports, so the deck stays a zero-dependency
  project. ~19 s cold, ~0.4 s warm, and the container image is cached afterwards.
  Non-fatal by design: a failed install warns and lets the session start, so a
  network blip never blocks slides work. Verified 2026-09-02:
  `python data/scripts/99_verify.py` → 19/19 pass.
- The catalog fetches read parquet/feather straight off
  `catalog.ourworldindata.org` — the `owid-catalog` library is **not** needed.
- **Headless render harness** (localhost is reachable in both):
  ```bash
  node dev-server.js &          # LOCAL: only if :4173 isn't already Joe's
  # cloud: playwright is installed by the hook and on $NODE_PATH
  # chromium.launch({ executablePath: process.env.CHROMIUM_PATH })
  # page.goto('http://localhost:4173/#<N>'); page.screenshot(...)
  ```
  Read the PNG back to eyeball layout/colours — the 1280×720 stage does not
  scroll, so overflow is invisible otherwise. Use `page.evaluate` to poke
  `Deck.data` / dispatch events to test interactivity (radios, dropdowns, draw
  tools); add `?edit` to test editor tools.
  In a **cloud** session **Google Fonts is blocked by the sandbox proxy**, so
  screenshots fall back to system fonts (a console `ERR_CONNECTION_RESET`). Not a
  bug — Playfair/Lato load fine on Joe's Mac and on Netlify. Don't "fix" it.
- **Palette validator**: dataviz skill →
  `node scripts/validate_palette.js "<hex,hex,...>" --mode light --pairs all`.
- Always `node --check` edited JS and `JSON.parse` edited JSON before committing.

## 10. Open threads / next steps

- **Q2 and Q3 are now built out** (slides 17–28: raw comparison, MLD explainer,
  the bridging chain, consumption→income and top-adjustment explainers, top-1%
  thresholds and treemaps), each backed by a `data/scripts/1N_fig_*.py` →
  `data/figures/fig_*.json` → `components/fig-*.js` chain. The data
  foundation behind them — see §12. Joe's prior research project
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
  slides 12 & 13 distinct headings (both currently under the Q1 kicker); the
  slide-8 table's Q3 row still has `??` cells; decide the fate of the demo slides
  (31–38) and the `demo-*` components, and of the superseded title slide 6.
- Offered-but-not-built: post-tax **disposable** WID variant (vs national income)
  on slides 10/11; per-region marker shapes for stronger CVD separation; an
  "add row / add column" control for `deck-table` in the editor.

## 11. File map

```
CLAUDE.md               # how Claude works in this repo (read first)
.claude/
  settings.json         # registers the SessionStart hook
  hooks/session-start.sh  # web-session setup: python deps + playwright
content/slides.json     # all slide content + per-slide annotations (SINGLE SOURCE OF TRUTH)
components/
  manifest.json         # list of component files to load
  gini-pip-wid-scatter.js   # Q1 slides 9–11 scatter (pre/post-tax, region highlight)
  ineq-trend.js             # Q1 slides 12–13 (trend + change scatters; two components)
  fig-*.js                  # Q2/Q3 figures — each FETCHES data/figures/fig_*.json
  demo-*.js                 # template demos (used only by demo slides 33/35/36)
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
