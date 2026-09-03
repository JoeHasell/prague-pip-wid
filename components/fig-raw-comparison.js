/* fig-raw-comparison.js — the "raw comparison" figure: WID vs PIP for three
 * countries (US, Indonesia, Nigeria), before any bridging adjustments.
 *
 * Two rows, one component:
 *   Row 1  Lollipops of P10, P90 and the country mean ($/month, shared LOG
 *          axis). WID pre-tax national income per adult on the left; PIP
 *          disposable income/consumption per capita on the right.
 *   Row 2  Stacked bars of the MLD *level*, decomposed into between- and
 *          within-country components, computed on the full 109-bin
 *          distributions of just these three countries — one bar per source,
 *          aligned under the corresponding row-1 group.
 *
 * DATA IS NOT EMBEDDED. The component fetches
 *     data/figures/fig_raw_comparison.json
 * which is produced by data/scripts/10_fig_raw_comparison.py — that script
 * (and data/README.md) documents all method choices (zero handling, weights).
 * Regenerating the JSON updates the figure; nothing here hard-codes numbers.
 *
 * Colours: countries use the Okabe-Ito palette (as elsewhere in this deck);
 * identity is also carried by direct labels under each lollipop. The MLD
 * components use a light/dark slate pair (lightness-separated, CVD-safe) and
 * are direct-labelled.
 *
 * BUILD-UP ACROSS SLIDES: the JSON contains ALL FIVE harmonized series; the
 * `sources` prop picks which columns to show, in order. The raw-comparison
 * slide shows two; the bridging-steps slide shows four. Adding another
 * bridging step to a slide = adding its series name to that slide's props.
 *
 * Props (all optional):
 *   dataUrl  override the JSON path
 *   title    chart title; pass "" (empty) to omit it — the lollipop row
 *            stretches up into the freed space
 *   reveal   subset of `sources` actually DRAWN, for building a chart up
 *            across consecutive slides. Every column in `sources` keeps its
 *            slot and both scales are still computed from all of them, so
 *            columns never shift and the axes never rescale as the build
 *            proceeds — only the marks appear. Unrevealed columns keep a
 *            faded header so the audience can see where the build is going.
 *            Omit to draw everything (the finished chart).
 *   sources  ordered array of series to show as columns, from:
 *            WID_pretax_per_adult | WID_pretax_per_capita |
 *            WID_posttax_per_adult | WID_posttax_per_capita | PIP
 *            (default: ["WID_pretax_per_adult", "PIP"])
 *   extremes true to also show the extreme bins (p0-p1 and the top 0.1%) as
 *            hollow circles. Zero-income p0-p1 bins (WID) are pinned at the
 *            axis floor — the tooltip states the true value is $0.
 */
Deck.registerComponent('fig-raw-comparison', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_raw_comparison.json';
  const COUNTRY_COLOR = {
    'United States': '#0072B2',
    'Indonesia': '#E69F00',
    'Nigeria': '#009E73',
  };
  const BETWEEN_C = '#3E5C76';   // dark slate  — between-country component
  const WITHIN_C = '#A9C0D6';    // light slate — within-country component

  el.innerHTML = `<div class="frc-loading">Loading figure data…</div>`;
  let dead = false;           // set by cleanup if the slide unmounts mid-fetch
  let cleanupInner = null;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) cleanupInner = render(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="frc-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/10_fig_raw_comparison.py</code> (${err.message})</div>`;
    });

  function render(data) {
    // undefined -> default title; empty string / false -> no title row
    const title = props.title === undefined
      ? 'Same countries, different pictures — before any adjustments'
      : (props.title || '');
    const hasTitle = !!title;
    const SOURCES = (Array.isArray(props.sources) && props.sources.length)
      ? props.sources : ['WID_pretax_per_adult', 'PIP'];
    // Two-line column headers: [what it measures, on what basis]
    const GROUP_LABEL = {
      WID_pretax_per_adult: ['WID — pre-tax national income', 'per adult'],
      WID_pretax_per_capita: ['WID — pre-tax national income', 'per capita'],
      WID_posttax_per_adult: ['WID — post-tax national income', 'per adult'],
      WID_posttax_per_capita: ['WID — post-tax national income', 'per capita'],
      PIP: ['PIP — disposable income or consumption', 'per capita'],
      PIP_topadj: ['PIP — top-adjusted with WID shape', 'per capita'],
      WID_posttax_rescaled: ['WID — post-tax, rescaled to adjusted PIP means', 'per capita'],
      PIP_consinc: ['PIP — consumption→income adjusted', 'per capita'],
    };
    // Compact headers for narrow columns (5+ sources)
    const GROUP_LABEL_SM = {
      WID_pretax_per_adult: ['WID pre-tax', 'per adult'],
      WID_pretax_per_capita: ['WID pre-tax', 'per capita'],
      WID_posttax_per_adult: ['WID post-tax', 'per adult'],
      WID_posttax_per_capita: ['WID post-tax', 'per capita'],
      PIP: ['PIP', 'per capita'],
      PIP_topadj: ['PIP top-adjusted', 'per capita'],
      WID_posttax_rescaled: ['WID post-tax', 'at adjusted PIP means'],
      PIP_consinc: ['PIP cons\u2192income', 'per capita'],
    };
    // Sources not present in the JSON render as GHOST columns (dashed
    // placeholder) — used to reserve space for planned bridging steps.
    const ghosts = new Set(SOURCES.filter(s => !data.mld.some(m => m.source === s)));
    // Build-up: `reveal` limits what is DRAWN, never what is measured or
    // laid out — SOURCES still drives nG, groupX and both scales.
    const REVEAL = Array.isArray(props.reveal) ? new Set(props.reveal) : null;
    const isOn = s => !REVEAL || REVEAL.has(s);
    // Emphasis: everything NOT listed is drawn faint. Entries are either a
    // source name ("PIP" — the whole column, lollipops and total included) or a
    // single bar segment ("PIP.between" / "PIP.within"). Like `reveal`, this
    // changes only what is painted — never the layout, scales or measurement,
    // so an emphasis slide sits on top of a build-up frame without moving.
    const EMPH = Array.isArray(props.emphasis) && props.emphasis.length ? props.emphasis : null;
    const DIM = ` opacity="${props.dimOpacity != null ? props.dimOpacity : 0.16}"`;
    // is this source mentioned at all (as a column or via one of its segments)?
    const emphHas = src => EMPH.some(e => e === src || e.indexOf(src + '.') === 0);
    // dim attribute for one piece; `part` null means the whole column
    const dimFor = (src, part) => {
      if (!EMPH) return '';
      const hit = EMPH.indexOf(src) !== -1 || (part && EMPH.indexOf(src + '.' + part) !== -1);
      return hit ? '' : DIM;
    };
    const countries = data.meta.countries;
    const nG = SOURCES.length;

    // Which lollipop points exist for the shown sources — an all-countries
    // dataset has no per-country lollipops (data.lollipop is empty), which
    // switches the component into BARS-ONLY mode: row 1 is skipped entirely
    // and the MLD bars get the vertical space. (Must be computed BEFORE the
    // geometry block below, which branches on it.)
    const showExtremes = !!props.extremes;
    const shown = data.lollipop.filter(d => SOURCES.includes(d.source));
    const barsOnly = shown.length === 0;

    // ---------- geometry ----------
    const W = 1000, H = 640;
    const ML = 74, MR = 20;
    // Row 1 (lollipops) — starts higher when there is no title row
    const r1Top = hasTitle ? 64 : 38, r1Bot = 330, r1H = r1Bot - r1Top;
    // Row 2 (MLD bars) — the whole canvas in bars-only mode
    const r2Top = barsOnly ? (hasTitle ? 116 : 92) : 412;
    const r2Bot = 590, r2H = r2Bot - r2Top;
    const midGap = 14;                    // gap around each column divider
    const halfW = (W - ML - MR - (nG - 1) * 2 * midGap) / nG;   // width of one column
    const groupX = {};
    SOURCES.forEach((s, k) => { groupX[s] = ML + k * (halfW + 2 * midGap); });
    const slotX = (src, i) => groupX[src] + (i + 0.5) * (halfW / countries.length);
    // Short country labels when columns are narrow; 3-letter codes when tight
    const SHORT = { 'United States': 'USA' };
    const ISO3 = { 'United States': 'USA', 'Indonesia': 'IDN', 'Nigeria': 'NGA' };
    const cLabel = c => (nG >= 5 ? (ISO3[c] || c.slice(0, 3).toUpperCase())
      : nG > 2 ? (SHORT[c] || c) : c);

    // Row-1 log scale — domain derived from the values actually shown, so
    // derived series with lower/higher values never clip. (In bars-only mode
    // there are no row-1 values; feed a dummy so the scale math stays finite.)
    const vals = barsOnly ? [1] : shown.flatMap(d => [d.p10, d.p90, d.mean]
      .concat(showExtremes ? [d.p0, d.p999].filter(v => v > 0) : []));
    const step125 = (v, up) => {   // snap to the 1-2-5 tick ladder
      const e = Math.floor(Math.log10(v));
      const m = v / Math.pow(10, e);
      const ladder = up ? [1, 2, 5, 10].find(s => s >= m - 1e-9) : [10, 5, 2, 1].find(s => s <= m + 1e-9);
      return ladder * Math.pow(10, e);
    };
    const lo = step125(Math.min(...vals), false);
    // Snapping the top up a full 1-2-5 step can leave a half-empty decade
    // when extremes are shown, so cap just above the maximum instead.
    const hiSnap = step125(Math.max(...vals), true);
    const hi = hiSnap / Math.max(...vals) > 2 ? Math.max(...vals) * 1.12 : hiSnap;
    const y1 = v => r1Top + r1H * (1 - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)));
    const TICKS = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
      for (const m of [1, 2, 5]) {
        const t = m * Math.pow(10, e);
        if (t >= lo * 0.999 && t <= hi * 1.001) TICKS.push(t);
      }
    const money = v => v >= 100 ? '$' + Math.round(v).toLocaleString() : (v >= 10 ? '$' + v.toFixed(0) : '$' + (+v.toFixed(2)));

    // Row-2 linear scale, domain padded above the tallest bar (only the
    // sources actually shown)
    const maxTotal = Math.max(...data.mld.filter(m => SOURCES.includes(m.source)).map(m => m.total));
    const m2hi = Math.ceil(maxTotal * 11) / 10;   // modest headroom for the total label
    const y2 = v => r2Bot - (v / m2hi) * r2H;
    const t2 = [];
    for (let t = 0; t <= m2hi + 1e-9; t += 0.25) t2.push(Math.round(t * 100) / 100);

    // ---------- row 1: grid + lollipops ----------
    const grid1 = TICKS.map(t =>
      `<line x1="${ML}" x2="${W - MR}" y1="${y1(t)}" y2="${y1(t)}" class="frc-grid"/>` +
      `<text x="${ML - 10}" y="${y1(t) + 4}" text-anchor="end" class="frc-tick">${money(t)}</text>`
    ).join('');

    const lolli = data.lollipop.filter(d => SOURCES.includes(d.source) && isOn(d.source)).map(d => {
      const i = countries.indexOf(d.country);
      const x = slotX(d.source, i);
      const c = COUNTRY_COLOR[d.country] || '#555';
      const isRef = d.source === SOURCES[0] && i === 0;   // annotate first lollipop only
      const ann = isRef ? (
        `<text x="${x - 14}" y="${y1(d.p90) + 4}" text-anchor="end" class="frc-ann">P90</text>` +
        `<text x="${x - 14}" y="${y1(d.mean) + 4}" text-anchor="end" class="frc-ann">Mean</text>` +
        `<text x="${x - 14}" y="${y1(d.p10) + 4}" text-anchor="end" class="frc-ann">P10</text>` +
        (showExtremes ? `<text x="${x - 14}" y="${y1(d.p999) + 4}" text-anchor="end" class="frc-ann">Top 0.1%</text>` +
          `<text x="${x - 14}" y="${(d.p0 > 0 ? y1(d.p0) : r1Bot) + 4}" text-anchor="end" class="frc-ann">P0\u2013P1</text>` : '')) : '';
      // Extreme bins as HOLLOW circles; zero-income bins pinned at the floor
      const ext = !showExtremes ? '' : [
        ['P0\u2013P1', d.p0], ['Top 0.1%', d.p999],
      ].map(([k, v]) => {
        const yv = v > 0 ? y1(v) : r1Bot;
        const pinned = v > 0 ? '' : ' data-pinned="1"';
        return `<circle class="frc-pt" data-k="${k}" data-v="${v}"${pinned} data-c="${d.country}" data-s="${d.source}" cx="${x}" cy="${yv}" r="5.5" fill="#fff" stroke="${c}" stroke-width="2"/>`;
      }).join('');
      return (
        `<g${dimFor(d.source, null)}>` +
        ext +
        `<line x1="${x}" x2="${x}" y1="${y1(d.p10)}" y2="${y1(d.p90)}" stroke="${c}" stroke-width="2.5" stroke-opacity="0.75"/>` +
        `<circle class="frc-pt" data-k="P90" data-v="${d.p90}" data-c="${d.country}" data-s="${d.source}" cx="${x}" cy="${y1(d.p90)}" r="6.5" fill="${c}" stroke="#fff" stroke-width="1.5"/>` +
        `<circle class="frc-pt" data-k="P10" data-v="${d.p10}" data-c="${d.country}" data-s="${d.source}" cx="${x}" cy="${y1(d.p10)}" r="6.5" fill="${c}" stroke="#fff" stroke-width="1.5"/>` +
        `<rect class="frc-pt" data-k="Mean" data-v="${d.mean}" data-c="${d.country}" data-s="${d.source}" x="${x - 6.5}" y="${y1(d.mean) - 6.5}" width="13" height="13" transform="rotate(45 ${x} ${y1(d.mean)})" fill="#fff" stroke="${c}" stroke-width="2.5"/>` +
        `<text x="${x}" y="${r1Bot + 20}" text-anchor="middle" class="frc-country">${cLabel(d.country)}</text>` +
        ann +
        '</g>'
      );
    }).join('');

    const ghostBoxes = [...ghosts].filter(isOn).map(s => {
      const gx = groupX[s] + 10, gw = halfW - 20;
      const gbw = Math.min(130, Math.round(halfW * 0.62));   // matches barW
      return (
        `<rect x="${gx}" y="${r1Top + 14}" width="${gw}" height="${r1Bot - r1Top - 28}" rx="8" class="frc-ghost"/>` +
        `<text x="${gx + gw / 2}" y="${(r1Top + r1Bot) / 2 + 4}" text-anchor="middle" class="frc-ghost-t">forthcoming</text>` +
        `<rect x="${groupX[s] + halfW / 2 - gbw / 2}" y="${y2(0) - 90}" width="${gbw}" height="90" rx="4" class="frc-ghost"/>` +
        `<text x="${groupX[s] + halfW / 2}" y="${y2(0) - 40}" text-anchor="middle" class="frc-ghost-t">?</text>`
      );
    }).join('');

    const headBase = barsOnly ? r2Top - 6 : r1Top;   // where column headers sit
    const divider = SOURCES.slice(1).map(s =>
      `<line x1="${groupX[s] - midGap}" x2="${groupX[s] - midGap}" y1="${headBase - 34}" y2="${r2Bot}" class="frc-divider"/>`
    ).join('');
    const groupHeads = SOURCES.map(s => {
      const [l1, l2] = (nG >= 5 ? GROUP_LABEL_SM[s] : GROUP_LABEL[s]) || [s, ''];
      const cx = groupX[s] + halfW / 2;
      const dim = !isOn(s) ? ' opacity="0.3"' : (EMPH && !emphHas(s) ? DIM : '');
      return `<text x="${cx}" y="${headBase - 24}" text-anchor="middle"${dim} class="frc-group${nG > 2 ? ' frc-group-sm' : ''}">${l1}</text>` +
             `<text x="${cx}" y="${headBase - 9}" text-anchor="middle"${dim} class="frc-group-sub">${l2}</text>`;
    }).join('');

    // Marker-shape legend (the non-obvious encoding) — one horizontal row in
    // the top-right corner, on the title line, clear of both group headers.
    const legend =
      `<g transform="translate(${W - MR - 320},${hasTitle ? 18 : r2Top - 34})">` +
      (showExtremes
        ? `<g transform="translate(${-(W - MR - 320) + ML},${r1Bot + 24})">` +
          `<circle cx="4" cy="-4" r="5" fill="#fff" stroke="#8895a5" stroke-width="2"/>` +
          `<text x="14" y="0" class="frc-legend-t">hollow: extreme bins &mdash; P0&ndash;P1 and the top 0.1% ` +
          `(zero-income P0&ndash;P1 bins shown at the axis floor)</text></g>`
        : '') +
      `<g>` +
      `<circle cx="0" cy="0" r="5.5" fill="#8895a5" stroke="#fff" stroke-width="1"/>` +
      `<text x="10" y="4" class="frc-legend-t">P90 / P10</text>` +
      `<rect x="80" y="-5" width="10" height="10" transform="rotate(45 85 0)" fill="#fff" stroke="#8895a5" stroke-width="2"/>` +
      `<text x="96" y="4" class="frc-legend-t">Country mean</text>` +
      `<line x1="196" x2="208" y1="0" y2="0" stroke="#8895a5" stroke-width="2.5"/>` +
      `<text x="214" y="4" class="frc-legend-t">P10&ndash;P90 range</text>` +
      `</g></g>`;

    // ---------- row 2: MLD stacked bars ----------
    const grid2 = t2.map(t =>
      `<line x1="${ML}" x2="${W - MR}" y1="${y2(t)}" y2="${y2(t)}" class="frc-grid"/>` +
      `<text x="${ML - 10}" y="${y2(t) + 4}" text-anchor="end" class="frc-tick">${t.toFixed(2)}</text>`
    ).join('');

    const barW = Math.min(130, Math.round(halfW * 0.62));
    const bars = data.mld.filter(m => SOURCES.includes(m.source) && isOn(m.source)).map(m => {
      const cx = groupX[m.source] + halfW / 2;
      const x = cx - barW / 2;
      const yB = y2(m.between), yT = y2(m.total);
      const hB = r2Bot - yB;                       // between segment (baseline up)
      const hW = yB - yT - 2;                      // within on top, 2px surface gap
      // Shares of total, each rounded from its own value (so "0.85 (69%)"
      // reads correctly even when the two roundings don't sum to 100).
      const pctB = Math.round(m.between / m.total * 100);
      const pctW = Math.round(m.within / m.total * 100);
      // A one-line label ("Between 0.33 (28%)") is ~120px wide — wider than
      // the bar when many columns are shown, where overflowing white text
      // disappears against the page. So: one line when the bar is wide
      // enough, two lines (value / share) when the segment is tall enough,
      // and a label beside the bar as the last resort.
      const wide = barW >= 120;
      // Very narrow bars (6+ columns) get a slightly smaller label font so
      // white-on-dark text never extends past the fill and vanishes.
      const fs = barW < 92 ? ' style="font-size:11.5px"' : '';
      const segLabel = (yMid, cls, name, val, pctv, hSeg) => {
        // Very narrow bars can't fit the component word — value + share only
        // (identity still carried by colour, position and the tooltip).
        const nm = barW >= 74 ? `${name} ` : '';
        const one = `${nm}${val.toFixed(2)} (${pctv}%)`;
        if (wide && hSeg > 26)
          return `<text x="${cx}" y="${yMid + 4}" text-anchor="middle" class="${cls}">${one}</text>`;
        if (!wide && hSeg > 34)
          return `<text x="${cx}" y="${yMid - 3}" text-anchor="middle" class="${cls}"${fs}>${nm}${val.toFixed(2)}</text>` +
                 `<text x="${cx}" y="${yMid + 11}" text-anchor="middle" class="${cls}"${fs}>(${pctv}%)</text>`;
        if (hSeg > 26)
          return `<text x="${cx}" y="${yMid + 4}" text-anchor="middle" class="${cls}"${fs}>${val.toFixed(2)} (${pctv}%)</text>`;
        // Last chance to stay INSIDE: value + share at a smaller size. Worth a
        // tier of its own because the alternative below prints beside the bar,
        // where it lands on top of the neighbouring column (the PIP within
        // segment is ~22px tall in the six-column bridging frames, and its
        // out-of-bar label overlapped PIP cons->income).
        if (hSeg > 17)
          return `<text x="${cx}" y="${yMid + 3.5}" text-anchor="middle" class="${cls}" style="font-size:10.5px">${val.toFixed(2)} (${pctv}%)</text>`;
        // Out-of-bar fallback: flip to the left side near the right edge so
        // the label never runs off the chart.
        return x + barW + 100 > W - MR
          ? `<text x="${x - 6}" y="${yMid + 4}" text-anchor="end" class="frc-seglab-out">${one}</text>`
          : `<text x="${x + barW + 6}" y="${yMid + 4}" class="frc-seglab-out">${one}</text>`;
      };
      const labB = segLabel(r2Bot - hB / 2, 'frc-seglab frc-seglab-dark', 'Between', m.between, pctB, hB);
      const labW = segLabel(yT + 2 + hW / 2, 'frc-seglab', 'Within', m.within, pctW, hW);
      return (
        `<g${dimFor(m.source, 'between')}>` +
          `<rect class="frc-seg" data-comp="Between countries" data-v="${m.between}" data-share="${pctB}" data-s="${m.source}" x="${x}" y="${yB}" width="${barW}" height="${hB}" rx="0" fill="${BETWEEN_C}"/>` +
          labB +
        `</g>` +
        `<g${dimFor(m.source, 'within')}>` +
          `<rect class="frc-seg" data-comp="Within countries" data-v="${m.within}" data-share="${pctW}" data-s="${m.source}" x="${x}" y="${yT}" width="${barW}" height="${hW}" rx="4" fill="${WITHIN_C}"/>` +
          labW +
        `</g>` +
        `<g${EMPH && !emphHas(m.source) ? DIM : ''}>` +
          `<text x="${cx}" y="${yT - 8}" text-anchor="middle" class="frc-total">Total MLD ${m.total.toFixed(2)}</text>` +
        `</g>`
      );
    }).join('');

    const stepNote = nG > 2
      ? 'All columns derive from the same underlying data; only the income concept / population basis changes.'
      : 'Raw published concepts — no bridging adjustments.';
    const scope = data.meta.scope_note || 'the three countries';
    const sourceLines = props.source ? [props.source] : [
      `Data: WID.world and World Bank PIP (via OWID), 2023, international-$ per month. MLD (mean log deviation) computed on the full 109-bin distributions of ${scope}.`,
      `WID zero-income bins set to $${data.meta.zero_replacement_usd_per_day}/day in the underlying daily data for the MLD. ${stepNote} Pipeline: ${data.meta.generated_by || 'data/scripts/10_fig_raw_comparison.py'}`,
    ];

    el.innerHTML = `
      <style>
        .frc-wrap { position: relative; width: 100%; height: 100%; }
        .frc-svg { width: 100%; height: 100%; display: block; }
        .frc-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .frc-title { font: 700 20px var(--font-body); fill: var(--ink); }
        .frc-grid { stroke: rgb(235,238,242); stroke-width: 1; }
        .frc-tick { font: 12.5px var(--font-body); fill: rgb(87,114,145); }
        .frc-axis { font: 600 13.5px var(--font-body); fill: rgb(63,96,138); }
        .frc-group { font: 700 14.5px var(--font-body); fill: var(--ink); }
        .frc-group-sm { font: 700 12.5px var(--font-body); }
        .frc-group-sub { font: italic 12px var(--font-body); fill: rgb(87,114,145); }
        .frc-divider { stroke: rgb(210,218,228); stroke-width: 1; stroke-dasharray: 3 4; }
        .frc-ghost { fill: rgb(246,248,251); stroke: rgb(190,201,214); stroke-width: 1.5; stroke-dasharray: 6 5; }
        .frc-ghost-t { font: italic 13px var(--font-body); fill: rgb(140,155,175); }
        .frc-country { font: 600 13px var(--font-body); fill: rgb(60,72,88); }
        .frc-ann { font: italic 11.5px var(--font-body); fill: rgb(140,155,175); }
        .frc-legend-bg { fill: #fff; fill-opacity: 0.92; stroke: rgb(235,238,242); }
        .frc-legend-t { font: 12px var(--font-body); fill: rgb(60,72,88); }
        .frc-rowtitle { font: 700 15px var(--font-body); fill: var(--ink); }
        .frc-seg { cursor: pointer; }
        .frc-seglab { font: 600 12.5px var(--font-body); fill: rgb(40,55,75); }
        .frc-seglab-dark { fill: #fff; }
        .frc-seglab-out { font: 600 12.5px var(--font-body); fill: rgb(60,72,88); }
        .frc-total { font: 700 13px var(--font-body); fill: var(--ink); }
        .frc-share { font: italic 12.5px var(--font-body); fill: rgb(87,114,145); }
        .frc-source { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
        .frc-pt { cursor: pointer; }
        .frc-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%, -100%); background: rgb(0,33,71); color: #fff;
          font: 13px var(--font-body); padding: 7px 10px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      </style>
      <div class="frc-wrap">
        <svg class="frc-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
          ${hasTitle ? `<text x="${ML}" y="24" class="frc-title">${title}</text>` : ''}
          ${barsOnly ? '' : grid1}
          ${barsOnly ? '' : `<text transform="translate(16,${r1Top + r1H / 2}) rotate(-90)" text-anchor="middle" class="frc-axis">Income per month (int-$, log scale)</text>`}
          ${divider}
          ${groupHeads}
          ${barsOnly ? '' : lolli}
          ${barsOnly ? '' : legend}
          ${barsOnly
            /* bars-only: the row title is the only descriptive text — put it
               at the very top, above the column headers */
            ? `<text x="${ML}" y="${hasTitle ? 48 : 24}" class="frc-rowtitle">${data.meta.row2_title || 'MLD level, decomposed'}</text>`
            : `<text x="${ML}" y="${r2Top - 16}" class="frc-rowtitle">${data.meta.row2_title || 'Inequality across these three countries&rsquo; populations combined &mdash; MLD level, decomposed'}</text>`}
          ${grid2}
          <text transform="translate(16,${r2Top + r2H / 2}) rotate(-90)" text-anchor="middle" class="frc-axis">Mean log deviation</text>
          ${bars}
          ${ghostBoxes}
          ${sourceLines.map((t, i) =>
            `<text x="${ML}" y="${H - 6 - (sourceLines.length - 1 - i) * 15}" class="frc-source">${t}</text>`).join('')}
        </svg>
        <div class="frc-tip"></div>
      </div>`;

    // ---------- hover layer ----------
    const wrap = el.querySelector('.frc-wrap');
    const tip = el.querySelector('.frc-tip');
    const svg = el.querySelector('.frc-svg');
    const shortSrc = s => {
      const g = GROUP_LABEL[s];
      return g ? `${g[0].split(' — ')[0]} (${g[0].split(' — ')[1] || ''}, ${g[1]})`.replace('(, ', '(') : s;
    };

    function place(target) {
      const tr = target.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = (tr.left + tr.width / 2 - wr.left) + 'px';
      tip.style.top = (tr.top - wr.top - 6) + 'px';
      tip.style.opacity = '1';
    }
    function onOver(e) {
      const pt = e.target.closest && e.target.closest('.frc-pt');
      if (pt) {
        const val = pt.dataset.pinned
          ? '$0/month (zero-income bin, shown at axis floor)'
          : `${money(+pt.dataset.v)}/month`;
        tip.innerHTML = `<b>${pt.dataset.c}</b> — ${pt.dataset.k}<br>${val} &middot; ${shortSrc(pt.dataset.s)}`;
        place(pt); return;
      }
      const seg = e.target.closest && e.target.closest('.frc-seg');
      if (seg) {
        tip.innerHTML = `<b>${seg.dataset.comp}</b><br>MLD ${(+seg.dataset.v).toFixed(3)} (${seg.dataset.share}% of total) &middot; ${shortSrc(seg.dataset.s)}`;
        place(seg); return;
      }
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && (to.closest('.frc-pt') || to.closest('.frc-seg'))) return;
      tip.style.opacity = '0';
    }
    svg.addEventListener('mouseover', onOver);
    svg.addEventListener('mouseout', onOut);
    return () => {
      svg.removeEventListener('mouseover', onOver);
      svg.removeEventListener('mouseout', onOut);
    };
  }

  return () => { dead = true; if (cleanupInner) cleanupInner(); };
});
