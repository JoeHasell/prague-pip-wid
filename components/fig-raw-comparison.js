/* fig-raw-comparison.js — the "raw comparison" figure: WID vs PIP for three
 * countries (US, Indonesia, Nigeria), before any bridging adjustments.
 *
 * Two rows, one component:
 *   Row 1  Lollipops of P10, P90 and the country mean ($/day, shared LOG
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
 *   title    chart title
 *   sources  ordered array of series to show as columns, from:
 *            WID_pretax_per_adult | WID_pretax_per_capita |
 *            WID_posttax_per_adult | WID_posttax_per_capita | PIP
 *            (default: ["WID_pretax_per_adult", "PIP"])
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
    const title = props.title || 'Same countries, different pictures — before any adjustments';
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
    };
    // Compact headers for narrow columns (5+ sources)
    const GROUP_LABEL_SM = {
      WID_pretax_per_adult: ['WID pre-tax', 'per adult'],
      WID_pretax_per_capita: ['WID pre-tax', 'per capita'],
      WID_posttax_per_adult: ['WID post-tax', 'per adult'],
      WID_posttax_per_capita: ['WID post-tax', 'per capita'],
      PIP: ['PIP', 'per capita'],
      PIP_topadj: ['PIP top-adjusted', 'per capita'],
    };
    const missing = SOURCES.filter(s => !data.mld.some(m => m.source === s));
    if (missing.length) {
      el.innerHTML = `<div class="frc-loading">Series not in ${DATA_URL}: ${missing.join(', ')} — re-run the figure script.</div>`;
      return null;
    }
    const countries = data.meta.countries;
    const nG = SOURCES.length;

    // ---------- geometry ----------
    const W = 1000, H = 640;
    const ML = 74, MR = 20;
    // Row 1 (lollipops)
    const r1Top = 64, r1Bot = 330, r1H = r1Bot - r1Top;
    // Row 2 (MLD bars)
    const r2Top = 412, r2Bot = 590, r2H = r2Bot - r2Top;
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

    // Row-1 log scale
    const lo = 1, hi = 600;
    const y1 = v => r1Top + r1H * (1 - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)));
    const TICKS = [1, 2, 5, 10, 20, 50, 100, 200, 500];
    const money = v => v >= 100 ? '$' + Math.round(v) : (v >= 10 ? '$' + v.toFixed(0) : '$' + (+v.toFixed(2)));

    // Row-2 linear scale, domain padded above the tallest bar
    const maxTotal = Math.max(...data.mld.map(m => m.total));
    const m2hi = Math.ceil(maxTotal * 12) / 10;   // e.g. 1.185 -> 1.5-ish headroom
    const y2 = v => r2Bot - (v / m2hi) * r2H;
    const t2 = [];
    for (let t = 0; t <= m2hi + 1e-9; t += 0.25) t2.push(Math.round(t * 100) / 100);

    // ---------- row 1: grid + lollipops ----------
    const grid1 = TICKS.map(t =>
      `<line x1="${ML}" x2="${W - MR}" y1="${y1(t)}" y2="${y1(t)}" class="frc-grid"/>` +
      `<text x="${ML - 10}" y="${y1(t) + 4}" text-anchor="end" class="frc-tick">${money(t)}</text>`
    ).join('');

    const lolli = data.lollipop.filter(d => SOURCES.includes(d.source)).map(d => {
      const i = countries.indexOf(d.country);
      const x = slotX(d.source, i);
      const c = COUNTRY_COLOR[d.country] || '#555';
      const isRef = d.source === SOURCES[0] && i === 0;   // annotate first lollipop only
      const ann = isRef ? (
        `<text x="${x - 14}" y="${y1(d.p90) + 4}" text-anchor="end" class="frc-ann">P90</text>` +
        `<text x="${x - 14}" y="${y1(d.mean) + 4}" text-anchor="end" class="frc-ann">Mean</text>` +
        `<text x="${x - 14}" y="${y1(d.p10) + 4}" text-anchor="end" class="frc-ann">P10</text>`) : '';
      return (
        `<line x1="${x}" x2="${x}" y1="${y1(d.p10)}" y2="${y1(d.p90)}" stroke="${c}" stroke-width="2.5" stroke-opacity="0.75"/>` +
        `<circle class="frc-pt" data-k="P90" data-v="${d.p90}" data-c="${d.country}" data-s="${d.source}" cx="${x}" cy="${y1(d.p90)}" r="6.5" fill="${c}" stroke="#fff" stroke-width="1.5"/>` +
        `<circle class="frc-pt" data-k="P10" data-v="${d.p10}" data-c="${d.country}" data-s="${d.source}" cx="${x}" cy="${y1(d.p10)}" r="6.5" fill="${c}" stroke="#fff" stroke-width="1.5"/>` +
        `<rect class="frc-pt" data-k="Mean" data-v="${d.mean}" data-c="${d.country}" data-s="${d.source}" x="${x - 6.5}" y="${y1(d.mean) - 6.5}" width="13" height="13" transform="rotate(45 ${x} ${y1(d.mean)})" fill="#fff" stroke="${c}" stroke-width="2.5"/>` +
        `<text x="${x}" y="${r1Bot + 20}" text-anchor="middle" class="frc-country">${cLabel(d.country)}</text>` +
        ann
      );
    }).join('');

    const divider = SOURCES.slice(1).map(s =>
      `<line x1="${groupX[s] - midGap}" x2="${groupX[s] - midGap}" y1="${r1Top - 34}" y2="${r2Bot}" class="frc-divider"/>`
    ).join('');
    const groupHeads = SOURCES.map(s => {
      const [l1, l2] = (nG >= 5 ? GROUP_LABEL_SM[s] : GROUP_LABEL[s]) || [s, ''];
      const cx = groupX[s] + halfW / 2;
      return `<text x="${cx}" y="${r1Top - 24}" text-anchor="middle" class="frc-group${nG > 2 ? ' frc-group-sm' : ''}">${l1}</text>` +
             `<text x="${cx}" y="${r1Top - 9}" text-anchor="middle" class="frc-group-sub">${l2}</text>`;
    }).join('');

    // Marker-shape legend (the non-obvious encoding) — one horizontal row in
    // the top-right corner, on the title line, clear of both group headers.
    const legend =
      `<g transform="translate(${W - MR - 320},18)">` +
      `<circle cx="0" cy="0" r="5.5" fill="#8895a5" stroke="#fff" stroke-width="1"/>` +
      `<text x="10" y="4" class="frc-legend-t">P90 / P10</text>` +
      `<rect x="80" y="-5" width="10" height="10" transform="rotate(45 85 0)" fill="#fff" stroke="#8895a5" stroke-width="2"/>` +
      `<text x="96" y="4" class="frc-legend-t">Country mean</text>` +
      `<line x1="196" x2="208" y1="0" y2="0" stroke="#8895a5" stroke-width="2.5"/>` +
      `<text x="214" y="4" class="frc-legend-t">P10&ndash;P90 range</text>` +
      `</g>`;

    // ---------- row 2: MLD stacked bars ----------
    const grid2 = t2.map(t =>
      `<line x1="${ML}" x2="${W - MR}" y1="${y2(t)}" y2="${y2(t)}" class="frc-grid"/>` +
      `<text x="${ML - 10}" y="${y2(t) + 4}" text-anchor="end" class="frc-tick">${t.toFixed(2)}</text>`
    ).join('');

    const barW = Math.min(130, Math.round(halfW * 0.62));
    const bars = data.mld.filter(m => SOURCES.includes(m.source)).map(m => {
      const cx = groupX[m.source] + halfW / 2;
      const x = cx - barW / 2;
      const yB = y2(m.between), yT = y2(m.total);
      const hB = r2Bot - yB;                       // between segment (baseline up)
      const hW = yB - yT - 2;                      // within on top, 2px surface gap
      const pct = (m.between_share * 100).toFixed(0);
      const labB = hB > 26
        ? `<text x="${cx}" y="${r2Bot - hB / 2 + 4}" text-anchor="middle" class="frc-seglab frc-seglab-dark">Between ${m.between.toFixed(2)}</text>`
        : `<text x="${x + barW + 8}" y="${r2Bot - hB / 2 + 4}" class="frc-seglab-out">Between ${m.between.toFixed(2)}</text>`;
      const labW = hW > 26
        ? `<text x="${cx}" y="${yT + 2 + hW / 2 + 4}" text-anchor="middle" class="frc-seglab">Within ${m.within.toFixed(2)}</text>`
        : `<text x="${x + barW + 8}" y="${yT + 2 + hW / 2 + 4}" class="frc-seglab-out">Within ${m.within.toFixed(2)}</text>`;
      return (
        `<rect class="frc-seg" data-comp="Between countries" data-v="${m.between}" data-share="${pct}" data-s="${m.source}" x="${x}" y="${yB}" width="${barW}" height="${hB}" rx="0" fill="${BETWEEN_C}"/>` +
        `<rect class="frc-seg" data-comp="Within countries" data-v="${m.within}" data-share="${100 - pct}" data-s="${m.source}" x="${x}" y="${yT}" width="${barW}" height="${hW}" rx="4" fill="${WITHIN_C}"/>` +
        labB + labW +
        `<text x="${cx}" y="${yT - 8}" text-anchor="middle" class="frc-total">Total MLD ${m.total.toFixed(2)}</text>` +
        `<text x="${cx}" y="${r2Bot + 18}" text-anchor="middle" class="frc-share">${pct}% between countries</text>`
      );
    }).join('');

    const stepNote = nG > 2
      ? 'All columns derive from the same underlying data; only the income concept / population basis changes.'
      : 'Raw published concepts — no bridging adjustments.';
    const sourceLines = props.source ? [props.source] : [
      `Data: WID.world and World Bank PIP (via OWID), 2023, international-$ per day. MLD (mean log deviation) computed on the full 109-bin distributions of the three countries.`,
      `WID zero-income bins set to $${data.meta.zero_replacement_usd_per_day}/day for the MLD. ${stepNote} Pipeline: data/scripts/10_fig_raw_comparison.py`,
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
          <text x="${ML}" y="24" class="frc-title">${title}</text>
          ${grid1}
          <text transform="translate(16,${r1Top + r1H / 2}) rotate(-90)" text-anchor="middle" class="frc-axis">Income per day (int-$, log scale)</text>
          ${divider}
          ${groupHeads}
          ${lolli}
          ${legend}
          <text x="${ML}" y="${r2Top - 16}" class="frc-rowtitle">Inequality across these three countries&rsquo; populations combined &mdash; MLD level, decomposed</text>
          ${grid2}
          <text transform="translate(16,${r2Top + r2H / 2}) rotate(-90)" text-anchor="middle" class="frc-axis">Mean log deviation</text>
          ${bars}
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
        tip.innerHTML = `<b>${pt.dataset.c}</b> — ${pt.dataset.k}<br>${money(+pt.dataset.v)}/day &middot; ${shortSrc(pt.dataset.s)}`;
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
