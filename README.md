# Deck framework

A static, no-build-step slide deck with interactive components and two authoring paths that converge on the same file:

1. **Programmatic** — Claude (or you) edits `content/slides.json` and drops component modules into `components/`. This is how data analysis, visualizations, and tables get into slides.
2. **Point-and-click** — open the deck with `?edit` in the URL to edit text in place, reorder blocks and slides, and tweak component props, no code required.

Everything is plain HTML/CSS/JS. `git push` to a Netlify-connected repo publishes the deck.

## Quick start

```bash
node dev-server.js
# view:  http://localhost:4173
# edit:  http://localhost:4173/?edit
```

The dev server is a zero-dependency Node script. While it runs, the editor's **Save** button writes straight to `content/slides.json` (keeping a rolling backup at `content/slides.json.bak`). Any other static server also works for *viewing* (`npx serve`, Python's `http.server`) — you just lose direct save, and the editor falls back to downloading the file. Opening `index.html` via `file://` does **not** work, because the deck fetches its content with `fetch()`.

Presenting: arrow keys / PgUp / PgDn / Space to navigate, Home/End to jump, **N** toggles speaker notes, and `#4` in the URL deep-links to slide 4.

## Publishing (GitHub + Netlify)

```bash
git init && git add -A && git commit -m "New deck"
gh repo create my-deck --private --source=. --push   # or create the repo on github.com and push
```

Then in Netlify: **Add new site → Import an existing project**, pick the repo, leave build command empty, set publish directory to `.` (the included `netlify.toml` already declares this). Every push now redeploys.

The published site is view-only for the audience. `?edit` still works there, but edits live only in that browser until exported — nothing on the server can change. It's a hidden door, not a security hole.

## Starting a new deck from this framework

Copy this whole folder into the new project (or use it as a GitHub template repo), then replace the dummy content: rewrite `content/slides.json`, delete the three `demo-*.js` components once real ones exist, and update `components/manifest.json` to match. Nothing under `src/`, `index.html`, or `dev-server.js` needs to change per deck — those are the engine.

## How content works

`content/slides.json` is the single source of truth:

```jsonc
{
  "meta": {
    "title": "Shown as the page title",
    "accent": "#0E6E59"          // optional per-deck accent color
  },
  "slides": [
    {
      "id": "slide-unique-id",
      "layout": "default",        // or "title" (vertically centered)
      "class": "",                // optional extra CSS classes
      "notes": "Speaker notes, shown with the N key",
      "blocks": [ ... ]
    }
  ]
}
```

There are three block types.

**`html`** — rich text. Any HTML works; the theme styles `h1`, `h2`, `h3`, `p`, `ul`, `ol`, `code`, plus two helper classes: `class="kicker"` (small uppercase accent label, use one at the top of most slides) and `class="muted"` (secondary gray text).

```json
{ "id": "b-1", "type": "html", "html": "<h2>A heading</h2>" }
```

**`component`** — an interactive module, referenced by registered name. `props` is arbitrary JSON passed to the component. Without `height`, the component fills the slide's remaining vertical space (usually what you want); with `height`, it gets a fixed pixel height.

```json
{ "id": "b-2", "type": "component", "component": "demo-line-chart",
  "props": { "title": "GDP per capita", "unit": "%" }, "height": 380 }
```

**`row`** — side-by-side layout. `children` is an array of `html`/`component` blocks; an optional `width` on a child (e.g. `"42%"`) fixes its share, otherwise children split space evenly.

```json
{ "id": "b-3", "type": "row", "children": [
  { "id": "b-3a", "type": "html", "width": "40%", "html": "<p>The argument…</p>" },
  { "id": "b-3b", "type": "component", "component": "demo-scrubber", "props": {} }
] }
```

Every slide and block needs an `id`, unique within the file. Short random suffixes are fine (`b-x7k2p1`).

## Writing a component

A component is one self-contained file in `components/`, registered by name:

```js
// components/my-chart.js
Deck.registerComponent('my-chart', (el, props, ctx) => {
  // Build any DOM you like inside `el`. `props` comes from slides.json.
  // `ctx.accent` is the deck accent color; `ctx.editMode` is true under ?edit.
  el.innerHTML = `<div style="padding:24px">Hello, ${props.name || 'world'}</div>`;

  // Optionally return a cleanup function (remove listeners, timers, observers).
  return () => {};
});
```

Then add the filename to `components/manifest.json`. That's the whole integration — no imports, no build. Scope any `<style>` you emit under a unique class so components don't leak styles into each other. Components mount lazily when their slide is first shown. External libraries (d3, Plotly, …) can be vendored as extra files in `components/` and listed in the manifest *before* the components that use them, or loaded from a CDN inside the component. Embedding data directly in the component file or in `props` is simplest; a component can also `fetch()` a CSV/JSON file committed anywhere in the repo (e.g. a `data/` folder).

The three `demo-*.js` files are working reference implementations of the common patterns: an SVG chart with hover state, a sortable table driven by `props`, and a stateful control. Read them before writing a new component; delete them from real decks.

## Conventions for Claude working in a content project

When a deck project says "add this analysis as a slide" or "include this visualization", follow this recipe:

1. Read `content/slides.json` first — never regenerate it wholesale; edit it surgically so manual edits made in the browser survive.
2. For a chart/table/interactive element: write a new self-contained component file in `components/`, register a descriptive kebab-case name, add the filename to `components/manifest.json`, then reference it from a `component` block in the target slide. Prefer putting the *data* in `props` (or a fetched `data/` file) and the *rendering* in the component, so the user can tweak numbers via the Props editor.
3. For prose: use `html` blocks. One `kicker`, one heading, and at most ~5 short bullets or ~3 short paragraphs fit on a slide. Slides are a fixed 1280×720 canvas — content does not scroll, so verify it fits.
4. Assign fresh unique `id`s to anything you add. Never reuse or renumber existing ids — the editor's drafts key off them.
5. Preserve the user's manual text edits: if a block's `html` looks hand-written, don't rewrite it unless asked.
6. Sanity-check by running `node dev-server.js` and fetching the pages, or at minimum validating the JSON (`node -e "JSON.parse(require('fs').readFileSync('content/slides.json'))"`).
7. Don't touch `src/`, `index.html`, or `dev-server.js` in content projects. Framework changes belong in the framework repo.

## Editing workflow (how Save works)

The editor is **hybrid**. Save tries `POST /save`; if a dev server answers, the file on disk is updated in place. If not (e.g. on the published Netlify site, or under `npx serve`), the browser downloads `slides.json` and you replace `content/slides.json` with it. Either way, an autosaved draft sits in the browser's localStorage from the moment you start typing — if you reload with unsaved changes, a yellow bar offers to restore or discard the draft. **Export** always downloads, regardless of server.

One habit worth keeping: when both you and Claude are editing the same deck, save (or export and replace) before asking Claude for structural changes, so the JSON on disk reflects your latest text.

## File map

```
index.html            entry point; loads the engine, and the editor only under ?edit
content/slides.json   ALL deck content (the only file the editor writes)
components/           one JS file per interactive component + manifest.json
src/deck.js|deck.css  presentation engine + theme (styled after ourworldindata.org)
src/editor.js|css     the ?edit inline editor
dev-server.js         optional local server with direct save (zero dependencies)
netlify.toml          tells Netlify to publish the root, no build
```

## Troubleshooting

A blank page with a "Could not load content/slides.json" message means the deck was opened over `file://` or the JSON is invalid — run the dev server and check its console, or validate the JSON with the one-liner above. A block reading *"Component X is not registered"* means the name in `slides.json` doesn't match a `Deck.registerComponent` call, or the file is missing from `components/manifest.json`. If saves silently turn into downloads, the dev server isn't running (or you're on the published site) — that's the designed fallback, not a bug.
