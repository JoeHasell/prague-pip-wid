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

## Where this session is running — check this first

Two kinds of session work on this repo, and they have very different powers.
**Local is the default for this project.** In the desktop app's **Code** tab the
**Environment** selector offers Local / Cloud / SSH; pick **Local** and the
project folder.

| | **Local session** (preferred) | **Cloud session** |
|---|---|---|
| Files | Joe's actual working copy, `~/Documents/Claude/Projects/prague-pip-wid` | a fresh clone in an isolated VM — **no access to Joe's Mac** |
| Browser edits | visible the moment he hits Save | invisible; they must reach GitHub first |
| Stata | available → `00_fetch_wid.py` can run **only here** | not available |
| Dev server | Joe's own may already be on `:4173` | yours to start |
| Lives | until the app closes | keeps running with the laptop shut |

**Tell them apart:** `$CLAUDE_CODE_REMOTE` is `true` in a cloud session and unset
locally; the working directory is `/home/user/prague-pip-wid` in the cloud and the
`Documents/...` path on the Mac. Check before you reason about where files are.

Use **Cloud** only for long autonomous jobs Joe wants running with the laptop shut.
The app's **Continue in → Claude Code on the Web** pushes a local session there.

## Git protocol

Claude Code runs `git` normally. (The old rule "the assistant must never run git"
was a Cowork-bridge artifact — the bridge couldn't delete `.git/index.lock`, so any
git command broke Joe's next commit. That constraint is gone.)

- Work on the branch this session was assigned; commit and push there.
- Never push to `main`. Don't open a PR unless Joe asks.
- Joe does not use the command line. **Claude does the git work**, including for
  his own edits.

**In a local session — the normal case.** "I made a bunch of changes in the browser
— push them" is a request you can just do: he saved from `?edit`, so
`content/slides.json` on disk is already his latest. `git diff` it, sanity-check
that it parses, commit and push. Don't rewrite what he wrote; the diff is his text.

**In a cloud session — the fallback.** His browser edits are on his laptop and
unreachable. Say so plainly rather than hunting for them or reconstructing them
from memory: he pushes them from **GitHub Desktop**, then you `git pull`.

**The one two-writer trap that survives, in both kinds of session.** The `?edit`
editor holds the whole deck in the browser tab and writes the *whole file* on Save.
So if Claude edits `slides.json` while a tab is open on an older copy, Joe's next
Save silently reverts that work — no conflict, no warning. The rule:

> **After Claude touches `slides.json`, Joe reloads the browser before his next
> edit.** Say so explicitly in your reply every time you change that file.

Correspondingly, edit `slides.json` **surgically** — never regenerate it wholesale,
or you'll wipe hand-edits and blow up the diff (it's ~540 KB, mostly annotation
point arrays). `src/*`, `components/*` and `data/*` are Claude-only in practice
(the browser editor writes `slides.json` alone), so those never collide.

Call out **new files** explicitly in your reply (e.g. anything under
`content/images/`) — a missing image breaks the slide for everyone.

## Environment

### In a local session (Joe's Mac)

- **Don't fight his dev server.** If `:4173` is already answering, it's his — use
  it, don't start a second one and don't kill it. Only `src/` changes need a
  restart (ask him); `slides.json` changes need only a reload.
- The Python and Node here are his, not a clean container. Check before assuming a
  package is present, and prefer `pip install -r data/requirements.txt` over
  installing things ad hoc. The SessionStart hook deliberately **does not** run
  locally — his machine is his.
- **Stata lives here**, so this is the only place `00_fetch_wid.py` can run. Still
  don't run it casually: ~1–2 h, and the raw pull is a committed cache.

### In a cloud session (this container)

| | |
|---|---|
| Setup | `.claude/hooks/session-start.sh` runs at session start (cloud only) and installs the two things below. `$NODE_PATH` and `$CHROMIUM_PATH` are exported for you. |
| Node | v22; the deck itself has **no dependencies** — `node dev-server.js` serves on `:4173` |
| Python | 3.11; pandas + pyarrow come from the hook (`pip install -r data/requirements.txt` if you ever need it by hand) |
| Stata | **not available** → `00_fetch_wid.py` cannot run. Everything downstream of the committed raw cache can. |
| Chromium | preinstalled at `$CHROMIUM_PATH` (`/opt/pw-browsers/chromium`) — **never** run `playwright install`. The playwright package lives outside the repo in `~/.deck-tools`, on `$NODE_PATH`, so the repo stays dependency-free — don't `npm i` into the repo root. |
| Google Fonts | blocked by the sandbox proxy — headless screenshots fall back to system fonts. Not a bug; on Joe's Mac and on Netlify the Playfair/Lato faces load. |

### Verify a slide actually renders

Works in both kinds of session — localhost is reachable from inside the cloud
container too.

```bash
node dev-server.js &          # LOCAL: only if :4173 isn't already Joe's
# then, in a scratchpad script (cloud: playwright resolves via $NODE_PATH):
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
