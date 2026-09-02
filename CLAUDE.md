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

## Git protocol

Claude Code runs `git` normally now. (The old rule "the assistant must never run
git" was a Cowork-bridge artifact — the bridge couldn't delete `.git/index.lock`,
so any git command broke Joe's next GitHub Desktop commit. That constraint is gone
in a Claude Code checkout.)

- Work on the branch this session was assigned; commit and push there.
- Never push to `main`. Don't open a PR unless Joe asks.

**A web session cannot see Joe's Mac.** It is a separate clone in a cloud
container, with no bridge to his filesystem (that bridge was a Cowork feature and
is gone). So if Joe says *"I made changes in the browser — push them"*, the honest
answer from a web session is that those edits are on his laptop and unreachable
here: he commits and pushes them himself in **GitHub Desktop**, then you `git pull`.
Don't go looking for them, and don't reconstruct them from memory.

**The two-writer caveat, restated for git.** `content/slides.json` is edited from
two places: Joe's in-browser `?edit` editor on his Mac, and Claude in a clone.
It's one ~540 KB JSON file, so the two ways it goes wrong are merge conflicts and
— worse — a silent revert, when Joe saves from a browser holding a stale copy.
The ordering that avoids both:

1. Joe **Saves in the browser and pushes from GitHub Desktop** *before* handing
   over a slides task.
2. Claude **pulls** before starting structural work, edits `slides.json`
   **surgically** (never regenerate it wholesale), commits, pushes.
3. Joe **pulls in GitHub Desktop and reloads the browser** *before* his next edit.
   Skipping this is the silent-revert trap: the editor saves the whole file, so a
   Save from a tab loaded before Claude's push wipes that push.

`src/*`, `components/*` and `data/*` are Claude-only in practice (the browser
editor writes `slides.json` alone), so those rarely collide.

Call out **new files** explicitly in your reply (e.g. anything under
`content/images/`) — they're easy to miss in GitHub Desktop's changes list, and a
missing image breaks the slide for everyone.

## Environment (this cloud container)

| | |
|---|---|
| Setup | `.claude/hooks/session-start.sh` runs automatically at session start (web only) and installs the two things below. `$NODE_PATH` and `$CHROMIUM_PATH` are exported for you. |
| Node | v22; the deck itself has **no dependencies** — `node dev-server.js` serves on `:4173` |
| Python | 3.11; pandas + pyarrow come from the hook (`pip install -r data/requirements.txt` if you ever need it by hand) |
| Stata | **not available** → `00_fetch_wid.py` cannot run here. Everything downstream of the committed raw cache can. |
| Chromium | preinstalled at `$CHROMIUM_PATH` (`/opt/pw-browsers/chromium`) — **never** run `playwright install`. The playwright package lives outside the repo in `~/.deck-tools`, on `$NODE_PATH`, so the repo stays dependency-free — don't `npm i` into the repo root. |
| localhost | reachable from within the container (unlike the old Cowork sandbox), so you can serve *and* screenshot the deck yourself |
| Google Fonts | blocked by the sandbox proxy — headless screenshots fall back to system fonts. Not a bug; on Joe's Mac and on Netlify the Playfair/Lato faces load. |

### Verify a slide actually renders

```bash
node dev-server.js &                       # or: python3 -m http.server 8300
# then, in a script written to the scratchpad (playwright resolves via $NODE_PATH):
#   const { chromium } = require('playwright');
#   const b = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH });
#   await p.goto('http://localhost:4173/#26'); await p.screenshot({ path: ... });
```

Read the PNG back and look at it. Slides are a fixed **1280×720** canvas that does
not scroll — layout overflow is invisible unless you look. Use `page.evaluate` to
poke `Deck.data` or fire events to exercise dropdowns, radios and draw tools, and
add `?edit` to test the editor.

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
