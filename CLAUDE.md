# CLAUDE.md — working on this repo with Claude Code

**Read next:** [`PROJECT_NOTES.md`](PROJECT_NOTES.md) (what the deck is, its state,
data provenance, open threads) and [`data/README.md`](data/README.md) (the data
pipeline — read before touching anything under `data/`). [`README.md`](README.md)
documents the generic deck framework.

One-line summary: a static, no-build HTML slide deck for Joe Hasell's Prague talk
on global income inequality (PIP vs WID), plus a reproducible Python pipeline that
generates every figure's data.

## Division of labour

Joe authors the substance — the narrative, which data to show, the wording.
Claude builds the scaffolding: chart components, data pipeline steps, engine and
editor features, and keeping `content/slides.json` valid. **Don't invent narrative
or pick data without being asked.**

## Where this session runs

**Always local, on Joe's Mac** — the desktop app's **Code** tab, Environment =
**Local**, project folder `~/Documents/Claude/Projects/prague-pip-wid`. You read
and write his actual working copy: his browser edits are visible the moment he
hits Save, Stata is present, and his dev server may already be on `:4173`.

**Cloud sessions are not used on this project** (decided 2026-09-02). A cloud
container is an isolated VM with no access to the Mac — which is where the deck is
authored and where Stata lives — so it can't see Joe's browser edits and can't run
the WID fetch. There is deliberately **no SessionStart hook** (one existed briefly
and was removed): don't add one, and don't reintroduce cloud-vs-local branching
into these docs.

## Git protocol

**Joe commits and pushes; Claude edits files.** The division that actually
operates on this project (confirmed 2026-09-02):

- **Work directly on `main`.** No feature branches, no PRs — this is a one-author
  deck, not a shared codebase.
- **Claude leaves its work uncommitted.** Make the edits, verify them, and stop
  there. Joe reviews the changes in **GitHub Desktop** and commits and pushes from
  the app — that's where his GitHub credentials live (HTTPS password auth is
  disabled, so a command-line push fails anyway).
- **Don't commit, push, branch, merge, rebase or rewrite history unless Joe asks
  for that specific thing.** Committing on his behalf takes the review step away
  from him.
- **Read-only `git` is free and encouraged** — `status`, `log`, `diff`,
  `merge-base`, `merge-tree`, `show`. Use it to orient and to explain the repo's
  state. (The old ban on running `git` at all was a Cowork-bridge artifact: the
  bridge couldn't delete `.git/index.lock`, so any git command broke Joe's next
  commit. That constraint is gone.)
- **Say what you changed, and name every NEW file explicitly** — Desktop's
  changes list is long and a new file is easy to miss, and a missing image or
  component file breaks the slide for everyone.
- **If Desktop refuses to push** ("Newer Commits on Remote"), that's the remote
  being ahead, not a conflict. Dry-run the merge (`git merge-tree` against the
  merge base) to see whether the incoming commits touch the same files, tell Joe
  what he'll receive, then walk him through **Fetch → Pull → Push**. Joe is not
  comfortable with git: explain what each click does, don't just name it.

**Joe's browser edits are already on disk.** He saves from `?edit`, so
`content/slides.json` is his latest — `git diff` shows his text. Never rewrite it.

**The two-writer trap.** The `?edit` editor holds the whole deck in the browser
tab and writes the *whole file* on Save. So if Claude edits `slides.json` while a
tab is open on an older copy, Joe's next Save silently reverts that work — no
conflict, no warning. The rule:

> **After Claude touches `slides.json`, Joe reloads the browser before his next
> edit.** Say so explicitly in your reply every time you change that file.

Correspondingly, edit `slides.json` **surgically** — never regenerate it wholesale,
or you'll wipe hand-edits and blow up the diff (it's ~540 KB, mostly annotation
point arrays). `src/*`, `components/*` and `data/*` are Claude-only in practice
(the browser editor writes `slides.json` alone), so those never collide.

Call out **new files** explicitly in your reply (e.g. anything under
`content/images/`) — a missing image breaks the slide for everyone.

## Environment — Joe's Mac

- **Don't fight his dev server.** If `:4173` is already answering, it's his — use
  it, don't start a second one and don't kill it. Only `src/` changes need a
  restart (ask him); `slides.json` changes need only a reload.
- The Python and Node here are his, not a clean container: **Python 3.9.7** and
  **Node v16.9.1** (checked 2026-09-02). Write pipeline scripts for 3.9 — no
  `match`, no `X | Y` annotations evaluated at runtime. pandas and pyarrow are
  installed; check before assuming anything else is, and prefer
  `pip install -r data/requirements.txt` over installing things ad hoc. Don't
  install into his machine without asking.
- The deck itself has **no dependencies** — `node dev-server.js` serves on `:4173`.
  Don't `npm i` into the repo root; keeping it dependency-free is deliberate.
- **Stata lives here**, so this is the only place `00_fetch_wid.py` can run. Still
  don't run it casually: ~1–2 h, and the raw pull is a committed cache.

### Verify a slide actually renders

Use the **built-in browser pane** against Joe's dev server. There is **no
Playwright or Chromium on this Mac** — those came from the cloud hook that no
longer exists. Don't install them; the pane needs nothing.

1. `preview_start` with `url: http://localhost:4173/#<N>`. Start
   `node dev-server.js` first only if `:4173` isn't already answering — usually
   it is, and then it's Joe's.
2. `resize_window` to **1280×720** so the stage renders 1:1, then `screenshot`.
   The image returns scaled to 800×450 — faithful enough for layout; `zoom` on a
   region for detail.
3. `javascript_tool` pokes `Deck.data` or fires events to exercise dropdowns,
   radios and draw tools. Add `?edit` to the URL to test the editor.
4. `resize_window` with preset `desktop` when finished — an emulated size
   otherwise sticks to that tab.

Then actually look at the screenshot. Slides are a fixed **1280×720** canvas that
does not scroll, so layout overflow is invisible unless you look. (This route was
verified end to end on 2026-09-02.)

### Always, before committing

```bash
node -e "JSON.parse(require('fs').readFileSync('content/slides.json'))"   # deck content
node --check components/<edited>.js                                       # any edited JS
python data/scripts/99_verify.py                                          # any pipeline change (19 checks)
```

## Deck conventions

- `content/slides.json` is the single source of truth: slides → ordered `blocks`
  (`html` / `component` / `row`), plus an optional per-slide `annotations` array
  (the drawing layer, stage coords 0–1280 × 0–720).
- Every slide and block needs a **fresh unique `id`**. Never reuse or renumber
  existing ids — the browser editor's drafts key off them.
- Prose: one `kicker`, one heading, ≲5 short bullets. Tables use
  `<table class="deck-table">` (add `small`).
- A component is one self-contained file in `components/`, registered with
  `Deck.registerComponent(name, (el, props, ctx) => { ...; return cleanup })` and
  listed in `components/manifest.json`. Scope emitted `<style>` under a unique
  class. One file may register several components.
- **Figure components must fetch their data** from `data/figures/fig_*.json` — no
  hard-coded numbers in new component JS. The provenance chain is:
  `slide → components/fig-*.js → data/figures/fig_*.json → data/scripts/1N_fig_*.py → processed/ → raw/`.
  (`gini-pip-wid-scatter.js` and `ineq-trend.js` predate this rule and still embed
  their arrays.)
- Region colours: Okabe-Ito colourblind-safe palette
  (`#0072B2 #E69F00 #009E73 #CC79A7 #56B4E9 #D55E00 #7A3E9D`). Validate any new
  categorical palette with the dataviz skill's `scripts/validate_palette.js` —
  don't eyeball it.
- The deck displays incomes **per month**; the pipeline's internal unit is
  int-$ **per day** end to end, converted only when figure scripts write JSON
  (`config.DAILY_TO_MONTHLY`).

Unlike a vanilla copy of this framework, **`src/` is fair game here** — the
annotation/draw layer was added to `deck.js`/`editor.js` for this deck. README's
"don't touch `src/`" line applies to plain content projects. After an `src/` change
Joe must restart the dev server and hard-refresh; `slides.json`-only changes need
just a reload.

## Data pipeline rules

Full detail in `data/README.md`; the load-bearing ones:

- **Never re-run `00_fetch_wid.py` casually** — needs Stata, takes 1–2 h. The raw
  WID pull is a committed cache (`data/raw/wid/`, refreshed 2026-08-11).
- Everything builds on `data/processed/pip_wid_harmonized_2023.csv`.
- **Every MLD decomposition goes through `data/scripts/mld.py`**, weighting
  countries by WID demography matched to the series' basis. Never hand-roll one.
- Derived-series definitions live once, in their own module: `topadj.py`,
  `rescale.py`, `consinc.py`; the seven displayed scenarios in `scenarios.py`.
- Zeros are retained in the harmonized file — each analysis script must state its
  own zero-handling convention.
- Run `99_verify.py` after any pipeline change. It encodes two historical bugs
  (missing PPP conversion, wrong bin population weights) — a failure there is real.
