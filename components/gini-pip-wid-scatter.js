/* gini-pip-wid-scatter.js — interactive scatter of Gini from two sources.
 *
 * X: Gini from the World Bank's Poverty and Inequality Platform (PIP),
 *    disposable income, per capita.
 * Y: Gini from the World Inequality Database (WID), national income per
 *    adult — either PRE-tax or POST-tax, chosen by the `measure` prop.
 * One dot per country, coloured by World Bank PIP region. Reference year
 * ~2019 (nearest comparable survey, 2014-2019). Hover a dot for details.
 *
 * Axes are identical whichever measure is shown, so a pre-tax slide and a
 * post-tax slide line up exactly and can be flicked back and forth.
 *
 * Colours: Okabe-Ito colourblind-safe palette. Region identity is also
 * carried by the legend and the hover tooltip (not colour alone).
 *
 * Data: World Bank PIP and World Inequality Database (WID.world), with
 * processing by Our World in Data. Regions: World Bank PIP regions.
 *
 * Props (all optional):
 *   measure   "pretax" (default) or "posttax" — which WID series on Y
 *   title     chart title (defaults per measure)
 *   yLabel    y-axis label (defaults per measure)
 *   source    source note under the chart
 *   data      override the built-in [{c,p,wPre,wPost,r,y}] records
 *   min, max  axis domain (default 0.2 - 0.8, shared by both axes)
 */
Deck.registerComponent('gini-pip-wid-scatter', (el, props, ctx) => {
  // Data is fetched, not embedded: data/figures/fig_gini_scatter.json, written by
  // data/scripts/25_fig_scatters_from_etl.py from OWID's ETL. Pass `data` to
  // override it (an array of {c, p, wPre, wPost, r, y} rows).
  const DATA_URL = props.dataUrl || 'data/figures/fig_gini_scatter.json';
  if (Array.isArray(props.data)) return render(props.data);

  el.innerHTML = `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">Loading figure data…</div>`;
  let dead = false;
  let inner = null;
  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(json => { if (!dead) inner = render(json.countries); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">` +
        `Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/25_fig_scatters_from_etl.py</code> (${err.message})</div>`;
    });
  return () => { dead = true; if (inner) inner(); };

  function render(DATA) {

  const measure = props.measure === 'posttax' ? 'posttax' : 'pretax';
  const yKey = measure === 'posttax' ? 'wPost' : 'wPre';
  const taxWord = measure === 'posttax' ? 'post-tax' : 'pre-tax';

  // Optional highlight: keep a named set of countries in full colour and
  // fade all the others to the background. `highlight` is an array of
  // country names; `highlightGroup: "register"` uses the built-in list of
  // EU-SILC register-based-income countries (income taken from tax /
  // administrative records rather than self-reported in the survey).
  const REGISTER = ['Czechia', 'Denmark', 'Finland', 'Iceland', 'Ireland', 'Latvia',
    'Lithuania', 'Malta', 'Netherlands', 'Norway', 'Slovenia', 'Sweden', 'Switzerland'];
  const highlightSet = Array.isArray(props.highlight) ? new Set(props.highlight)
    : (props.highlightGroup === 'register' ? new Set(REGISTER) : null);

  const title = props.title || ((highlightSet && props.highlightGroup === 'register')
    ? 'Register-based countries: income taken from tax records'
    : (measure === 'posttax'
      ? 'The same comparison, with WID measured post-tax'
      : 'Two sources, two pictures of inequality'));
  const yLabel = props.yLabel || `Gini &mdash; WID (${taxWord} national, per adult)`;
  const source = props.source || (`Data: World Bank PIP and World Inequality Database (WID.world), via Our World in Data. Gini index, reference year ≈ 2019. WID = ${taxWord} national income. Regions: World Bank PIP.`
    + (highlightSet ? ' Highlighted: register-based-income countries.' : ''));
  const lo = props.min ?? 0.2, hi = props.max ?? 0.8;

  // Region -> colour. Fixed order (Okabe-Ito, colourblind-safe).
  const REGIONS = [
    'Sub-Saharan Africa', 'Other high income countries', 'Europe and Central Asia',
    'East Asia and Pacific', 'Middle East and North Africa', 'South Asia',
    'Latin America and the Caribbean',
  ];
  const PALETTE = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00', '#000000'];
  const colorOf = r => PALETTE[Math.max(0, REGIONS.indexOf(r)) % PALETTE.length];
  // Legend shows only regions that have a visible (non-faded) dot — so in
  // highlight mode it lists just the highlighted countries' regions.
  const regionsPresent = REGIONS.filter(r => DATA.some(d => (!highlightSet || highlightSet.has(d.c)) && d.r === r));

  const W = 1000, H = 600;
  const M = { top: 46, right: 26, bottom: 66, left: 70 };
  const plotW = W - M.left - M.right, plotH = H - M.top - M.bottom;
  const px = v => M.left + ((v - lo) / (hi - lo)) * plotW;
  const py = v => M.top + plotH - ((v - lo) / (hi - lo)) * plotH;

  const fmt = v => v.toFixed(2);
  const ticks = [];
  for (let t = lo; t <= hi + 1e-9; t += 0.1) ticks.push(Math.round(t * 100) / 100);

  const grid = ticks.map(t =>
    `<line x1="${px(t)}" x2="${px(t)}" y1="${M.top}" y2="${M.top + plotH}" class="gp-grid"/>` +
    `<line x1="${M.left}" x2="${M.left + plotW}" y1="${py(t)}" y2="${py(t)}" class="gp-grid"/>` +
    `<text x="${px(t)}" y="${M.top + plotH + 22}" text-anchor="middle" class="gp-tick">${fmt(t)}</text>` +
    `<text x="${M.left - 12}" y="${py(t) + 4}" text-anchor="end" class="gp-tick">${fmt(t)}</text>`
  ).join('');

  const diag = `<line x1="${px(lo)}" y1="${py(lo)}" x2="${px(hi)}" y2="${py(hi)}" class="gp-diag"/>` +
    `<text x="${px(hi) - 6}" y="${py(hi) + 20}" text-anchor="end" class="gp-diaglabel">Sources agree</text>`;

  // Build dots. In highlight mode, dimmed points are drawn first so the
  // highlighted (full-colour) points sit on top. Each dot stores its base
  // radius so hover can restore the right size.
  function dotSVG(d, i) {
    const on = !highlightSet || highlightSet.has(d.c);
    const baseR = !highlightSet ? 6.5 : (on ? 7 : 5);
    const fill = on ? colorOf(d.r) : '#c2c9d4';
    const op = !highlightSet ? 0.85 : (on ? 0.95 : 0.4);
    const stroke = on ? 1.5 : 0.75;
    return `<circle class="gp-dot" data-i="${i}" data-baser="${baseR}" cx="${px(d.p)}" cy="${py(d[yKey])}" ` +
      `r="${baseR}" fill="${fill}" fill-opacity="${op}" stroke="#fff" stroke-width="${stroke}"/>`;
  }
  const order = DATA.map((d, i) => [d, i]);
  if (highlightSet) order.sort((a, b) => (highlightSet.has(a[0].c) ? 1 : 0) - (highlightSet.has(b[0].c) ? 1 : 0));
  const dots = order.map(([d, i]) => dotSVG(d, i)).join('');

  // Legend, lower-right (empty triangle below the diagonal). Width sized
  // to the longest region label so long WB names don't clip.
  const legendW = 250, rowH = 22;
  const lgX = M.left + plotW - legendW + 8;
  const lgY = M.top + plotH - regionsPresent.length * rowH - 16;
  const legend = `<g class="gp-legend" transform="translate(${lgX},${lgY})">` +
    `<rect x="-12" y="-16" width="${legendW}" height="${regionsPresent.length * rowH + 20}" rx="6" class="gp-legend-bg"/>` +
    regionsPresent.map((r, i) =>
      `<circle cx="0" cy="${i * rowH}" r="6" fill="${colorOf(r)}" stroke="#fff" stroke-width="1"/>` +
      `<text x="14" y="${i * rowH + 4}" class="gp-legend-t">${r}</text>`
    ).join('') + `</g>`;

  el.innerHTML = `
    <style>
      .gp-wrap { position: relative; width: 100%; height: 100%; }
      .gp-svg { width: 100%; height: 100%; display: block; }
      .gp-title { font: 700 20px var(--font-body); fill: var(--ink); }
      .gp-grid { stroke: rgb(235, 238, 242); stroke-width: 1; }
      .gp-tick { font: 13px var(--font-body); fill: rgb(87, 114, 145); }
      .gp-axis { font: 600 14px var(--font-body); fill: rgb(63, 96, 138); }
      .gp-diag { stroke: rgb(160, 175, 194); stroke-width: 1.5; stroke-dasharray: 5 4; }
      .gp-diaglabel { font: italic 12px var(--font-body); fill: rgb(140, 155, 175); }
      .gp-dot { cursor: pointer; transition: r 0.08s ease; }
      .gp-legend-bg { fill: #fff; fill-opacity: 0.92; stroke: rgb(235, 238, 242); }
      .gp-legend-t { font: 12.5px var(--font-body); fill: var(--ink); }
      .gp-source { font: 12px var(--font-body); fill: rgb(140, 155, 175); }
      .gp-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
        transform: translate(-50%, -100%); background: rgb(0, 33, 71); color: #fff;
        font: 13px var(--font-body); padding: 8px 11px; border-radius: 6px;
        white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      .gp-tip b { font-weight: 700; }
      .gp-tip .gp-tip-row { color: rgba(255,255,255,0.82); margin-top: 3px; }
      .gp-tip .gp-sw { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
    </style>
    <div class="gp-wrap">
      <svg class="gp-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        <text x="${M.left}" y="26" class="gp-title">${title}</text>
        ${grid}
        ${diag}
        <text transform="translate(18,${M.top + plotH / 2}) rotate(-90)" text-anchor="middle" class="gp-axis">${yLabel}</text>
        <text x="${M.left + plotW / 2}" y="${H - 22}" text-anchor="middle" class="gp-axis">Gini &mdash; World Bank PIP (disposable, per capita)</text>
        ${dots}
        ${legend}
        <text x="${M.left}" y="${H - 4}" class="gp-source">${source}</text>
      </svg>
      <div class="gp-tip"></div>
    </div>`;

  const wrap = el.querySelector('.gp-wrap');
  const tip = el.querySelector('.gp-tip');

  function showTip(d, circle) {
    const cr = circle.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
    tip.style.left = (cr.left + cr.width / 2 - wr.left) + 'px';
    tip.style.top = (cr.top - wr.top - 6) + 'px';
    const diff = ((d[yKey] - d.p) * 100).toFixed(0);
    const rel = diff >= 0 ? `WID higher by ${diff}` : `WID lower by ${-diff}`;
    tip.innerHTML =
      `<div><span class="gp-sw" style="background:${colorOf(d.r)}"></span><b>${d.c}</b> <span style="opacity:.7">(${d.y})</span></div>` +
      `<div class="gp-tip-row">${d.r}</div>` +
      `<div class="gp-tip-row">PIP Gini: ${d.p.toFixed(3)}</div>` +
      `<div class="gp-tip-row">WID Gini (${taxWord}): ${d[yKey].toFixed(3)}</div>` +
      `<div class="gp-tip-row">${rel} points</div>`;
    tip.style.opacity = '1';
  }
  function hideTip() { tip.style.opacity = '0'; }

  const svg = el.querySelector('.gp-svg');
  let activeDot = null;
  function resetActive() { if (activeDot) { activeDot.setAttribute('r', activeDot.dataset.baser || '6.5'); activeDot = null; } }
  function onOver(e) {
    const circle = e.target.closest && e.target.closest('.gp-dot');
    if (!circle || circle === activeDot) return;
    resetActive(); activeDot = circle; circle.setAttribute('r', '9.5');
    showTip(DATA[+circle.dataset.i], circle);
  }
  function onOut(e) {
    const circle = e.target.closest && e.target.closest('.gp-dot');
    if (!circle) return;
    const to = e.relatedTarget;
    if (to && to.closest && to.closest('.gp-dot')) return;
    resetActive(); hideTip();
  }
  function onWrapLeave() { resetActive(); hideTip(); }
  svg.addEventListener('mouseover', onOver);
  svg.addEventListener('mouseout', onOut);
  wrap.addEventListener('mouseleave', onWrapLeave);
  return () => {
    svg.removeEventListener('mouseover', onOver);
    svg.removeEventListener('mouseout', onOut);
    wrap.removeEventListener('mouseleave', onWrapLeave);
  };
}
});
