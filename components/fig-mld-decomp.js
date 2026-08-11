/* fig-mld-decomp.js — pedagogical anatomy of the MLD decomposition, for the
 * slide-12 pair of series (WID pre-tax per adult vs PIP) and the three
 * highlight countries.
 *
 * The idea: on a LOG income axis, log-gaps are visible DISTANCES. For every
 * person,  ln(mu/x) = ln(mu/mu_c) + ln(mu_c/x)  — their gap to the overall
 * mean is their country's gap (between, dark) plus their own gap within
 * their country (within, light). The MLD is the population-weighted average
 * of those gaps, so the stacked bar at the right of each panel is literally
 * the average of the annotated arrows. Colours match the decomposition bars
 * used on the neighbouring slides.
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_mld_decomp_explainer.json
 * (produced by data/scripts/12_fig_mld_decomp_explainer.py, which follows
 * the project's MLD conventions in mld.py).
 *
 * Props (all optional):
 *   dataUrl   override the JSON path
 */
Deck.registerComponent('fig-mld-decomp', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_mld_decomp_explainer.json';
  const COUNTRY_COLOR = {
    'United States': '#0072B2', 'Indonesia': '#E69F00', 'Nigeria': '#009E73',
  };
  const BETWEEN_C = '#3E5C76';   // dark slate — between-country component
  const WITHIN_C = '#A9C0D6';    // light slate — within-country component
  const WITHIN_ARROW = '#7FA1C4';  // mid tone so the within arrow reads on white
  const WC_C = '#7A3E9D';         // population weights w_c (appears in BOTH formula terms)
  const MLDC_C = '#4d729b';       // per-country MLD_c (the within term's other factor)

  el.innerHTML = `<div class="fmd-loading">Loading figure data…</div>`;
  let dead = false;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) render(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="fmd-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/12_fig_mld_decomp_explainer.py</code> (${err.message})</div>`;
    });

  function render(data) {
    const W = 1400, H = 500;
    const LBL = 138;                    // right edge of country labels
    const WX0 = 150, WBARMAX = 86;      // population-weight column (w_c)
    const MLDX = 234;                   // per-country MLD_c column
    const X0 = 288, X1 = 1150;          // shared log axis
    const BARX = 1235, BARW = 64;       // mini stacked bar per panel
    const panels = [
      { top: 66, bot: 240 },            // WID
      { top: 300, bot: 474 },           // PIP
    ];

    // Shared log x-domain from the data
    const allVals = data.sources.flatMap(s => s.countries.flatMap(c =>
      Object.values(c.deciles).concat([c.mean, s.mu])));
    const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...allVals))));
    const hi5 = Math.max(...allVals);
    let hi = Math.pow(10, Math.ceil(Math.log10(hi5)));
    if (hi / hi5 > 2) hi = hi / 2;      // avoid a mostly-empty last decade
    const X = v => X0 + (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * (X1 - X0);
    const TICKS = [];
    for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
      for (const m of [1, 2, 5]) {
        const t = m * Math.pow(10, e);
        if (t >= lo * 0.999 && t <= hi * 1.001) TICKS.push(t);
      }
    const money = v => v >= 100 ? '$' + Math.round(v).toLocaleString()
      : v >= 10 ? '$' + v.toFixed(0)
      : v >= 1 ? '$' + (v % 1 === 0 ? v : v.toFixed(1)) : '$' + v.toFixed(2);

    // Bar scale shared across panels so the two bars are comparable
    const maxTotal = Math.max(...data.sources.map(s => s.total));
    const BARH_MAX = 128;
    const bh = v => v / maxTotal * BARH_MAX;

    const hover = [];
    let outSvg = '';

    // x grid + ticks (drawn per panel band, labels once at the very bottom)
    panels.forEach(p => {
      outSvg += TICKS.map(t =>
        `<line x1="${X(t)}" x2="${X(t)}" y1="${p.top}" y2="${p.bot - 22}" class="fmd-grid"/>`).join('');
    });
    outSvg += TICKS.map(t =>
      `<text x="${X(t)}" y="${panels[1].bot - 4}" text-anchor="middle" class="fmd-tick">${money(t)}</text>`).join('');

    data.sources.forEach((s, pi) => {
      const p = panels[pi];
      const rowY = i => p.top + 26 + i * 44;

      outSvg += `<text x="${X0}" y="${p.top + 2}" class="fmd-ptitle">${s.label}</text>`;
      // population-weight column header (basis differs by panel!)
      outSvg += `<text x="${WX0}" y="${p.top + 2}" class="fmd-whead" fill="${WC_C}">w<tspan baseline-shift="sub" font-size="9">c</tspan> (${s.weight_basis})</text>`;
      outSvg += `<text x="${MLDX}" y="${p.top + 2}" class="fmd-whead" fill="${MLDC_C}">MLD<tspan baseline-shift="sub" font-size="9">c</tspan></text>`;

      // Overall mean: dashed line through the panel
      outSvg += `<line x1="${X(s.mu)}" x2="${X(s.mu)}" y1="${p.top + 8}" y2="${p.bot - 22}" class="fmd-mu"/>`;
      outSvg += `<text x="${X(s.mu) + 6}" y="${p.top + 16}" class="fmd-mulab">overall mean &mu; = ${money(s.mu)}</text>`;

      s.countries.forEach((c, i) => {
        const y = rowY(i);
        const col = COUNTRY_COLOR[c.country] || '#555';
        const dec = Object.values(c.deciles);
        // baseline for the row
        outSvg += `<line x1="${X(Math.min(...dec))}" x2="${X(Math.max(...dec))}" y1="${y}" y2="${y}" stroke="${col}" stroke-width="1.5" stroke-opacity="0.45"/>`;
        // decile dots ("people")
        Object.entries(c.deciles).forEach(([bin, v]) => {
          outSvg += `<circle class="fmd-pt" data-h="${hover.length}" cx="${X(v)}" cy="${y}" r="4.5" fill="${col}" fill-opacity="0.85" stroke="#fff" stroke-width="1"/>`;
          hover.push({ t: `<b>${c.country}</b> ${bin}<br>${money(v)}/month` });
        });
        // country mean diamond
        outSvg += `<rect class="fmd-pt" data-h="${hover.length}" x="${X(c.mean) - 7}" y="${y - 7}" width="14" height="14" transform="rotate(45 ${X(c.mean)} ${y})" fill="#fff" stroke="${col}" stroke-width="2.5"/>`;
        hover.push({ t: `<b>${c.country}</b> mean &mu;<sub>c</sub><br>${money(c.mean)}/month &middot; within-MLD ${c.within_mld.toFixed(2)}` });
        // row label
        outSvg += `<text x="${LBL}" y="${y + 4}" text-anchor="end" class="fmd-country" fill="${col}">${c.country}</text>`;
        // population weight: small bar + percentage (hover for absolute)
        const wbar = c.pop_share * WBARMAX;
        const popM = (c.pop / 1e6).toFixed(0);
        outSvg += `<rect class="fmd-pt" data-h="${hover.length}" x="${WX0}" y="${y - 6}" width="${wbar.toFixed(1)}" height="12" rx="2" fill="${WC_C}" fill-opacity="0.30"/>`;
        outSvg += `<text x="${WX0 + wbar + 5}" y="${y + 4}" class="fmd-wpct" fill="${WC_C}">${(c.pop_share * 100).toFixed(0)}%</text>`;
        hover.push({ t: `<b>${c.country}</b> weight w<sub>c</sub><br>${(c.pop_share * 100).toFixed(1)}% of the three countries&rsquo; ${s.weight_basis} (${popM}M)` });
        // per-country MLD_c — the within term's other factor, in its colour
        outSvg += `<text x="${MLDX}" y="${y + 4}" class="fmd-mldc" fill="${MLDC_C}">${c.within_mld.toFixed(2)}</text>`;
      });

      // Annotated example gaps on the LAST row (Nigeria): x = P10 dot
      const nga = s.countries[s.countries.length - 1];
      const y = rowY(s.countries.length - 1) + 20;
      const xP10 = X(nga.deciles['p10p11']), xMean = X(nga.mean), xMu = X(s.mu);
      const arrow = (xa, xb, color, id) =>
        `<line x1="${xa}" x2="${xb - 6}" y1="${y}" y2="${y}" stroke="${color}" stroke-width="2.5" marker-end="url(#${id})"/>` +
        `<line x1="${xa}" x2="${xa}" y1="${y - 5}" y2="${y + 5}" stroke="${color}" stroke-width="2"/>`;
      outSvg += arrow(xP10, xMean, WITHIN_ARROW, 'fmd-aw');
      outSvg += arrow(xMean, xMu, BETWEEN_C, 'fmd-ab');
      const gapW = Math.log(nga.mean / nga.deciles['p10p11']);
      const gapB = Math.log(s.mu / nga.mean);
      outSvg += `<text x="${(xP10 + xMean) / 2}" y="${y + 16}" text-anchor="middle" class="fmd-gaplab" fill="#4d729b">within gap ln(&mu;<tspan baseline-shift="sub" font-size="9">c</tspan>/x) = ${gapW.toFixed(1)}</text>`;
      outSvg += `<text x="${(xMean + xMu) / 2}" y="${y + 16}" text-anchor="middle" class="fmd-gaplab" fill="${BETWEEN_C}">between gap ln(&mu;/&mu;<tspan baseline-shift="sub" font-size="9">c</tspan>) = ${gapB.toFixed(1)}</text>`;

      // Mini stacked bar: the population-weighted average of all those gaps
      const yBase = p.bot - 26;
      const hB = bh(s.between), hW = bh(s.within);
      outSvg += `<rect x="${BARX}" y="${yBase - hB}" width="${BARW}" height="${hB}" fill="${BETWEEN_C}"/>`;
      outSvg += `<rect x="${BARX}" y="${yBase - hB - 2 - hW}" width="${BARW}" height="${hW}" rx="3" fill="${WITHIN_C}"/>`;
      outSvg += `<text x="${BARX + BARW + 8}" y="${yBase - hB / 2 + 4}" class="fmd-barlab" fill="${BETWEEN_C}">Between ${s.between.toFixed(2)}</text>`;
      outSvg += `<text x="${BARX + BARW + 8}" y="${yBase - hB - 2 - hW / 2 + 4}" class="fmd-barlab" fill="#4d729b">Within ${s.within.toFixed(2)}</text>`;
      outSvg += `<text x="${BARX}" y="${yBase - hB - hW - 12}" class="fmd-bartot">MLD ${s.total.toFixed(2)}</text>`;
      outSvg += `<text x="${BARX}" y="${yBase + 14}" class="fmd-barnote">= avg. of the gaps</text>`;
    });

    const legendY = 16;
    el.innerHTML = `
      <style>
        .fmd-wrap { position: relative; width: 100%; height: 100%; }
        .fmd-svg { width: 100%; height: 100%; display: block; }
        .fmd-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .fmd-title { font: 700 19px var(--font-body); fill: var(--ink); }
        .fmd-grid { stroke: rgb(238,241,245); stroke-width: 1; }
        .fmd-tick { font: 12px var(--font-body); fill: rgb(87,114,145); }
        .fmd-ptitle { font: 700 14px var(--font-body); fill: var(--ink); }
        .fmd-country { font: 600 13px var(--font-body); }
        .fmd-whead { font: italic 11.5px var(--font-body); fill: rgb(100,118,140); }
        .fmd-wpct { font: 600 11.5px var(--font-body); }
        .fmd-mldc { font: 700 12px var(--font-body); }
        .fmd-mu { stroke: rgb(120,135,155); stroke-width: 1.5; stroke-dasharray: 5 4; }
        .fmd-mulab { font: italic 12px var(--font-body); fill: rgb(100,118,140); }
        .fmd-gaplab { font: italic 12px var(--font-body); }
        .fmd-barlab { font: 700 12.5px var(--font-body); }
        .fmd-bartot { font: 700 13px var(--font-body); fill: var(--ink); }
        .fmd-barnote { font: italic 11.5px var(--font-body); fill: rgb(120,135,155); }
        .fmd-legend-t { font: 12px var(--font-body); fill: rgb(60,72,88); }
        .fmd-pt { cursor: pointer; }
        .fmd-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%, -100%); background: rgb(0,33,71); color: #fff;
          font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      </style>
      <div class="fmd-wrap">
        <svg class="fmd-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
          <defs>
            <marker id="fmd-aw" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${WITHIN_ARROW}"/></marker>
            <marker id="fmd-ab" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${BETWEEN_C}"/></marker>
          </defs>
          <text x="${WX0}" y="20" class="fmd-title">Log-distances: each person&rsquo;s gap to the overall mean = between gap + within gap</text>
          <g transform="translate(${W - 460},${legendY})">
            <circle cx="0" cy="-4" r="4.5" fill="#8895a5" stroke="#fff"/><text x="9" y="0" class="fmd-legend-t">deciles (p10&hellip;p90)</text>
            <rect x="138" y="-10" width="11" height="11" transform="rotate(45 143 -4)" fill="#fff" stroke="#8895a5" stroke-width="2"/><text x="153" y="0" class="fmd-legend-t">country mean &mu;<tspan baseline-shift="sub" font-size="9">c</tspan></text>
            <line x1="268" x2="284" y1="-4" y2="-4" stroke="rgb(120,135,155)" stroke-width="1.5" stroke-dasharray="5 4"/><text x="290" y="0" class="fmd-legend-t">overall mean &mu;</text>
          </g>
          ${outSvg}
        </svg>
        <div class="fmd-tip"></div>
      </div>`;

    const wrap = el.querySelector('.fmd-wrap');
    const tip = el.querySelector('.fmd-tip');
    const svg = el.querySelector('.fmd-svg');
    function onOver(e) {
      const pt = e.target.closest && e.target.closest('.fmd-pt');
      if (!pt) return;
      const cr = pt.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = (cr.left + cr.width / 2 - wr.left) + 'px';
      tip.style.top = (cr.top - wr.top - 6) + 'px';
      tip.innerHTML = hover[+pt.dataset.h].t;
      tip.style.opacity = '1';
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.fmd-pt')) return;
      tip.style.opacity = '0';
    }
    svg.addEventListener('mouseover', onOver);
    svg.addEventListener('mouseout', onOut);
    // capture hover array in closure for handlers
    const hoverRef = hover; void hoverRef;
    cleanup = () => {
      svg.removeEventListener('mouseover', onOver);
      svg.removeEventListener('mouseout', onOut);
    };
  }

  let cleanup = null;
  return () => { dead = true; if (cleanup) cleanup(); };
});
