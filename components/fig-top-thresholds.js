/* fig-top-thresholds.js — Q3 opener: the ENTRY income for the global
 * top 10% / top 1% / top 0.1%, compared across the seven scenarios of the
 * Q2 bridging charts (same column order and headers as fig-raw-comparison).
 *
 * One vertical lollipop per scenario on a shared log axis, with three
 * markers (circle = top 10%, diamond = top 1%, triangle = top 0.1%) and the
 * dollar value labelled next to each marker.
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_top_thresholds.json,
 * produced by data/scripts/15_fig_top_thresholds.py (thresholds over the
 * 211-country common sample, basis-matched populations — the per-adult
 * scenario ranks the world's ADULTS).
 *
 * Props (all optional):
 *   dataUrl  override the JSON path
 *   title    undefined -> default title; '' -> no title row
 */
Deck.registerComponent('fig-top-thresholds', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_top_thresholds.json';

  el.innerHTML = `<div class="ftt-loading">Loading figure data…</div>`;
  let dead = false;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) render(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="ftt-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/15_fig_top_thresholds.py</code> (${err.message})</div>`;
    });

  function render(data) {
    const title = props.title === undefined
      ? 'What income gets you into the global top 10%, 1%, 0.1%?'
      : (props.title || '');
    const hasTitle = !!title;

    // Two-line column headers, matching fig-raw-comparison's compact set
    const SHORT = {
      WID_pretax_per_adult: ['WID pre-tax', 'per adult'],
      WID_pretax_per_capita: ['WID pre-tax', 'per capita'],
      WID_posttax_per_capita: ['WID post-tax', 'per capita'],
      WID_posttax_rescaled: ['WID post-tax', 'at adjusted PIP means'],
      PIP_topadj: ['PIP top-adjusted', 'per capita'],
      PIP_consinc: ['PIP cons→income', 'per capita'],
      PIP: ['PIP', 'per capita'],
    };
    const TIERS = [
      { key: 'top10',  label: 'Top 10%',  color: '#8FB0D1', shape: 'circle' },
      { key: 'top1',   label: 'Top 1%',   color: '#3E5C76', shape: 'diamond' },
      { key: 'top0_1', label: 'Top 0.1%', color: '#0B2545', shape: 'triangle' },
    ];
    const rows = data.thresholds;
    const nG = rows.length;

    // ---------- geometry ----------
    const W = 1000, H = 640;
    const ML = 84, MR = 20;
    const headBase = 64;   // legend and (optional) title share the y=20 line
    const pTop = headBase + 26, pBot = 556;
    const midGap = 12;
    const colW = (W - ML - MR - (nG - 1) * 2 * midGap) / nG;
    const colX = k => ML + k * (colW + 2 * midGap);
    const cx = k => colX(k) + colW / 2 - 22;   // marker x (labels sit right)

    const vals = rows.flatMap(r => TIERS.map(t => r[t.key]));
    const step125 = (v, up) => {   // snap to the 1-2-5 tick ladder
      const e = Math.floor(Math.log10(v));
      const m = v / Math.pow(10, e);
      const s = up ? [1, 2, 5, 10].find(x => x >= m - 1e-9) : [10, 5, 2, 1].find(x => x <= m + 1e-9);
      return s * Math.pow(10, e);
    };
    const lo = step125(Math.min(...vals), false);
    const hi = step125(Math.max(...vals), true);
    const y = v => pBot - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * (pBot - pTop);
    const TICKS = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
      for (const m of [1, 2, 5]) {
        const t = m * Math.pow(10, e);
        if (t >= lo * 0.999 && t <= hi * 1.001) TICKS.push(t);
      }
    const money = v => '$' + (v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(0));

    // ---------- marks ----------
    const grid = TICKS.map(t =>
      `<line x1="${ML}" x2="${W - MR}" y1="${y(t)}" y2="${y(t)}" class="ftt-grid"/>` +
      `<text x="${ML - 10}" y="${y(t) + 4}" text-anchor="end" class="ftt-tick">${money(t)}</text>`
    ).join('');

    const divider = rows.slice(1).map((r, k) =>
      `<line x1="${colX(k + 1) - midGap}" x2="${colX(k + 1) - midGap}" y1="${headBase - 34}" y2="${pBot}" class="ftt-divider"/>`
    ).join('');

    const heads = rows.map((r, k) => {
      const [l1, l2] = SHORT[r.source] || [r.source, ''];
      const mid = colX(k) + colW / 2;
      return `<text x="${mid}" y="${headBase - 24}" text-anchor="middle" class="ftt-group">${l1}</text>` +
             `<text x="${mid}" y="${headBase - 9}" text-anchor="middle" class="ftt-group-sub">${l2}</text>`;
    }).join('');

    const marker = (shape, x, yy, c) => {
      if (shape === 'circle') return `<circle cx="${x}" cy="${yy}" r="6" fill="${c}" stroke="#fff" stroke-width="1.2"/>`;
      if (shape === 'diamond') return `<path d="M${x},${yy - 7.5}L${x + 7.5},${yy}L${x},${yy + 7.5}L${x - 7.5},${yy}Z" fill="${c}" stroke="#fff" stroke-width="1.2"/>`;
      return `<path d="M${x},${yy - 7.5}L${x + 7.2},${yy + 5.6}L${x - 7.2},${yy + 5.6}Z" fill="${c}" stroke="#fff" stroke-width="1.2"/>`;
    };

    const lollis = rows.map((r, k) => {
      const x = cx(k);
      let out = `<line x1="${x}" x2="${x}" y1="${y(r.top10)}" y2="${y(r.top0_1)}" class="ftt-stem"/>`;
      TIERS.forEach(t => {
        const v = r[t.key];
        out += marker(t.shape, x, y(v), t.color);
        out += `<text x="${x + 13}" y="${y(v) + 4}" class="ftt-val" fill="${t.color}">${money(v)}</text>`;
      });
      return out;
    }).join('');

    // Chip legend, top right on the title line
    const legY = 20;
    let lx = W - MR - TIERS.reduce((w, t) => w + t.label.length * 6.8 + 34, 0);
    const legend = TIERS.map(t => {
      const s = marker(t.shape, lx + 7, legY - 4, t.color) +
        `<text x="${lx + 18}" y="${legY}" class="ftt-leg" fill="${t.color}">${t.label}</text>`;
      lx += t.label.length * 6.8 + 34;
      return s;
    }).join('');

    const src = [
      `Data: WID.world and World Bank PIP (via OWID), ${data.meta.year}, international-$ per month. Entry income = the average income of the marginal country-bin at the global cutoff, over ${data.meta.n_countries} countries.`,
      `Per-adult scenario ranks the world's adults; per-capita scenarios rank all people (WID demography throughout). Pipeline: ${data.meta.generated_by}`,
    ].map((s, i) => `<text x="${ML}" y="${pBot + 40 + i * 15}" class="ftt-src">${s}</text>`).join('');

    el.innerHTML = `
      <style>
        .ftt-wrap { width: 100%; height: 100%; }
        .ftt-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .ftt-svg { width: 100%; height: 100%; display: block; }
        .ftt-title { font: 700 19px var(--font-body); fill: var(--ink); }
        .ftt-grid { stroke: rgb(238,241,245); stroke-width: 1; }
        .ftt-tick { font: 12px var(--font-body); fill: rgb(87,114,145); }
        .ftt-divider { stroke: rgb(226,231,238); stroke-width: 1; }
        .ftt-group { font: 700 13.5px var(--font-body); fill: var(--ink); }
        .ftt-group-sub { font: italic 12px var(--font-body); fill: rgb(87,114,145); }
        .ftt-stem { stroke: rgb(200,210,222); stroke-width: 2; }
        .ftt-val { font: 700 12.5px var(--font-body); }
        .ftt-ann { font: italic 12px var(--font-body); fill: rgb(120,135,155); }
        .ftt-leg { font: 700 12.5px var(--font-body); }
        .ftt-axis { font: 600 13px var(--font-body); fill: rgb(63,96,138); }
        .ftt-src { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
      </style>
      <div class="ftt-wrap">
        <svg class="ftt-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
          ${hasTitle ? `<text x="${ML}" y="24" class="ftt-title">${title}</text>` : ''}
          ${grid}
          <text transform="translate(20,${(pTop + pBot) / 2}) rotate(-90)" text-anchor="middle" class="ftt-axis">Entry income per month (int-$, log scale)</text>
          ${divider}
          ${heads}
          ${legend}
          ${lollis}
          ${src}
        </svg>
      </div>`;
  }

  return () => { dead = true; };
});
