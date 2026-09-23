/* fig-refyear-scatter.js — inequality in one year against another, with the years
 * chosen on the slide, for PIP's adjusted series and WID.
 *
 * Registers TWO components sharing one fetched dataset:
 *   refyear-scatter         two panels (a PIP series | a WID series), each a scatter of
 *                           a country's inequality in year A (x) vs year B (y).
 *                           45-degree line = no change; above it inequality rose.
 *   refyear-change-scatter  one scatter of the CHANGE in the PIP series (x) against the
 *                           change in the WID series (y) over the same two years.
 *
 * Both carry a control bar: metric, year A, year B, which PIP series (as published /
 * income basis / top 1% appended), which WID series (pre-tax / post-tax per capita),
 * a same-welfare switch, and — on the change scatter — absolute vs relative change.
 *
 * Data: data/figures/fig_refyear_scatter.json, written by
 * data/scripts/34_fig_refyear_scatter.py from the reference-year dataset. For each
 * series and country it holds one slot per reference year: the SURVEY year actually
 * used (`y`), its welfare concept (`w`: i / c / -) and the four measures. PIP values
 * are matched to the nearest survey within five years, so a pair is drawn only when
 *   - both years have a value,
 *   - the two survey years differ (one survey can serve several reference years), and
 *   - unless switched off, both surveys use the same welfare concept —
 * the rules of refyears.pair(). WID has every year, so its pairs are always exact.
 *
 * FILLED basis (`basis: "filled"` or the "PIP data" switch): the PIP side instead reads
 * `series_filled` — PIP's lined-up estimate at every year for the 171 countries with a
 * national survey (37_filled_year_indicators.py). Every country with both years is drawn
 * (the same-welfare filter still applies); there is no "different surveys" rule, so a dot
 * is drawn HOLLOW when either year is extrapolated — its distribution is mostly the edge
 * survey's, so the change is largely mechanical. The tooltip names each year's kind.
 *
 * Props (all optional):
 *   metric       "gini" (default) | "top10" | "top1" | "palma"
 *   metrics      which of those to offer (default all four)
 *   yearA, yearB the two years (default 1993 and 2019, the ETL's comparison)
 *   pipSeries    "PIP" | "PIP_consinc" | "PIP_topadj" (default) | "PIP_consinc_wb" |
 *                "PIP_topadj_wb" (the same chain on the Wollburg et al. income basis)
 *   widSeries    "WID_pretax_per_capita" | "WID_posttax_per_capita" (default)
 *   sameWelfare  false to allow income-vs-consumption pairs on the PIP side (default true)
 *   basis        "nearest_survey" (default) | "filled" — the PIP side's data (see above)
 *   mode         change scatter only: "abs" (default) | "rel"
 *   controls     false to hide the control bar (a fixed talk slide)
 *   source       the source line under the chart
 */
(function () {
  const DATA_URL = 'data/figures/fig_refyear_scatter.json';
  let dataPromise = null;
  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch(DATA_URL)
        .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); });
    }
    return dataPromise;
  }
  function withData(el, build) {
    el.innerHTML = `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">Loading figure data…</div>`;
    let dead = false, inner = null;
    loadData()
      .then(D => { if (!dead) inner = build(D); })
      .catch(err => {
        if (!dead) el.innerHTML =
          `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">` +
          `Could not load ${DATA_URL} — run <code>python data/scripts/34_fig_refyear_scatter.py</code> (${err.message})</div>`;
      });
    return () => { dead = true; if (inner) inner(); };
  }

  const METRICS = {
    gini:  { label: 'Gini',          tick: v => v.toFixed(2),        val: v => v.toFixed(3),       dch: v => v.toFixed(3) },
    top10: { label: 'Top 10% share', tick: v => Math.round(v) + '%', val: v => v.toFixed(1) + '%', dch: v => v.toFixed(1) + 'pp' },
    top1:  { label: 'Top 1% share',  tick: v => Math.round(v) + '%', val: v => v.toFixed(1) + '%', dch: v => v.toFixed(1) + 'pp' },
    palma: { label: 'Palma ratio',   tick: v => v.toFixed(1),        val: v => v.toFixed(2),       dch: v => v.toFixed(2) },
  };
  const SHORT = {
    PIP: 'PIP, as published', PIP_consinc: 'PIP, income basis', PIP_topadj: "PIP + WID's top 1%",
    // the parallel chain on the Wollburg et al. (2023) income basis (consinc.py)
    PIP_consinc_wb: 'PIP, income basis (Wollburg)', PIP_topadj_wb: "PIP + WID's top 1% (Wollburg)",
    WID_pretax_per_capita: 'WID pre-tax', WID_posttax_per_capita: 'WID post-tax',
  };
  const WELFARE = { i: 'income', c: 'consumption', '-': '' };
  const KIND = { s: 'survey', i: 'interpolated', e: 'extrapolated' };
  const BASES = { nearest_survey: 'Nearest survey', filled: 'Filled' };
  const SOURCE = {
    nearest_survey: 'Data: World Bank PIP and WID.world via Our World in Data; measures computed from the harmonized distributions. PIP matched to its nearest survey within five years of each year shown.',
    filled: "Data: World Bank PIP and WID.world via Our World in Data; measures computed from the harmonized distributions. PIP's lined-up estimate at each year (171 countries with a national survey); hollow dots: an extrapolated year at either end.",
  };
  const REGIONS = ['Sub-Saharan Africa', 'Other high income countries', 'Europe and Central Asia',
    'East Asia and Pacific', 'Middle East and North Africa', 'South Asia', 'Latin America and the Caribbean'];
  const PALETTE = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00', '#7A3E9D'];
  const colorOf = r => { const i = REGIONS.indexOf(r); return i < 0 ? '#9AA5B1' : PALETTE[i]; };

  function niceNum(x, round) {
    const exp = Math.floor(Math.log10(x)); const f = x / Math.pow(10, exp);
    let nf; if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
    else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return nf * Math.pow(10, exp);
  }
  function axis(lo, hi, n) {
    if (!isFinite(lo) || !isFinite(hi)) { lo = 0; hi = 1; }
    if (hi === lo) { hi = lo + 1; }
    const range = niceNum(hi - lo, false);
    const step = niceNum(range / Math.max(1, n - 1), true);
    const glo = Math.floor(lo / step) * step, ghi = Math.ceil(hi / step) * step;
    const ticks = []; for (let v = glo; v <= ghi + step * 0.5; v += step) ticks.push(Math.round(v / step) * step);
    return { ticks, lo: glo, hi: ghi };
  }

  const STYLE = `
    <style>
      .ry-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
      .ry-controls { display: flex; gap: 14px 22px; flex-wrap: wrap; align-items: center; padding: 2px 4px 6px; font: 14px var(--font-body); color: var(--ink); }
      .ry-controls .grp { display: flex; gap: 10px; align-items: center; }
      .ry-controls .grp-label { font: 700 11px var(--font-body); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
      .ry-controls label { display: inline-flex; gap: 5px; align-items: center; cursor: pointer; }
      .ry-controls input { accent-color: var(--accent); cursor: pointer; }
      .ry-controls select { font: 14px var(--font-body); color: var(--ink); padding: 2px 6px; border: 1px solid rgb(200, 210, 222); border-radius: 5px; background: #fff; cursor: pointer; }
      .ry-plot { flex: 1; min-height: 0; }
      .ry-svg { width: 100%; height: 100%; display: block; }
      .ry-title { font: 700 16px var(--font-body); fill: var(--ink); }
      .ry-sub { font: 13px var(--font-body); fill: rgb(87, 114, 145); }
      .ry-grid { stroke: rgb(235, 238, 242); stroke-width: 1; }
      .ry-tick { font: 12px var(--font-body); fill: rgb(87, 114, 145); }
      .ry-axis { font: 600 13px var(--font-body); fill: rgb(63, 96, 138); }
      .ry-diag { stroke: rgb(160, 175, 194); stroke-width: 1.5; stroke-dasharray: 5 4; }
      .ry-zero { stroke: rgb(120, 140, 165); stroke-width: 1; }
      .ry-note { font: italic 11px var(--font-body); fill: rgb(140, 155, 175); }
      .ry-empty { font: italic 14px var(--font-body); fill: rgb(140, 155, 175); }
      .ry-dot { cursor: pointer; transition: r 0.08s ease; }
      .ry-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 6px 4px 0; font: 12px var(--font-body); color: var(--ink); }
      .ry-legend span.k { display: inline-flex; gap: 6px; align-items: center; }
      .ry-legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
      .ry-source { padding: 4px 4px 0; font: 11px var(--font-body); color: rgb(140, 155, 175); }
      .ry-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0; transform: translate(-50%, -100%);
        background: rgb(0, 33, 71); color: #fff; font: 13px var(--font-body); padding: 8px 11px; border-radius: 6px;
        white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      .ry-tip b { font-weight: 700; } .ry-tip .r { color: rgba(255,255,255,0.82); margin-top: 3px; }
      .ry-tip .sw { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
    </style>`;

  function legendHTML(rows) {
    const present = REGIONS.filter(r => rows.some(d => d.r === r));
    return present.map(r => `<span class="k"><i style="background:${colorOf(r)}"></i>${r}</span>`).join('');
  }

  // The PIP side switches block with the basis; WID is the same under both.
  const filledOn = (D, series, basis) => basis === 'filled' && D.series_filled && D.series_filled[series];
  const block = (D, series, basis) => (filledOn(D, series, basis) ? D.series_filled[series] : D.series[series]);

  // A country's value for `series`/`metric` at reference year index i, or null.
  function slot(D, series, c, metric, i, basis) {
    const s = block(D, series, basis)[c];
    if (!s || s[metric][i] == null) return null;
    return { v: s[metric][i], y: s.y ? s.y[i] : null, w: s.w[i], k: s.k ? s.k[i] : null, d: s.d ? s.d[i] : null };
  }

  // The pairs the rules allow: both years present, survey years differ, and (PIP
  // side, when asked) the same welfare concept at both ends.
  function pairs(D, series, metric, ia, ib, sameWelfare, basis) {
    const out = [];
    const filled = filledOn(D, series, basis);
    Object.keys(block(D, series, basis)).forEach(c => {
      const a = slot(D, series, c, metric, ia, basis), b = slot(D, series, c, metric, ib, basis);
      if (!a || !b) return;
      if (!filled && a.y === b.y) return;
      if (sameWelfare && a.w !== '-' && b.w !== '-' && a.w !== b.w) return;
      out.push({ c, r: D.countries[c].r, a: a.v, b: b.v, ya: a.y, yb: b.y, wa: a.w, wb: b.w,
        ka: a.k, kb: b.k, da: a.d, db: b.d, ext: filled && (a.k === 'e' || b.k === 'e') });
    });
    return out;
  }

  function surveyNote(d, side) {
    // "survey 1995 (income)" for PIP; on the filled basis the kind of year instead
    // ("extrapolated, 4 yrs from a survey"); nothing for WID, whose year IS the reference year
    const y = side === 'a' ? d.ya : d.yb, w = side === 'a' ? d.wa : d.wb;
    const k = side === 'a' ? d.ka : d.kb, dist = side === 'a' ? d.da : d.db;
    const wl = WELFARE[w] ? ' (' + WELFARE[w] + ')' : '';
    if (k) {
      const what = k === 's' ? 'survey' : `${KIND[k]}, ${dist} yr${dist === 1 ? '' : 's'} from a survey`;
      return ` <span style="opacity:.7">— ${what}${wl}</span>`;
    }
    return w === '-' ? '' : ` <span style="opacity:.7">— survey ${y}${wl}</span>`;
  }

  // Hollow for a filled pair with an extrapolated end, solid otherwise.
  const dotPaint = (d, color) => (d.ext
    ? `fill="#fff" fill-opacity="1" stroke="${color}" stroke-width="1.8"`
    : `fill="${color}" fill-opacity="0.82" stroke="#fff" stroke-width="1.2"`);

  function yearSelect(name, years, value) {
    return `<select name="${name}">${years.map(y => `<option value="${y}" ${y === value ? 'selected' : ''}>${y}</option>`).join('')}</select>`;
  }
  // Short labels in the dropdowns keep the control bar on one line; the panels
  // carry the full series names.
  function seriesSelect(name, keys, value) {
    return `<select name="${name}">${keys.map(k => `<option value="${k}" ${k === value ? 'selected' : ''}>${SHORT[k]}</option>`).join('')}</select>`;
  }

  function controlsHTML(D, st, keys, withMode) {
    return `<div class="ry-controls">
      <span class="grp"><span class="grp-label">Metric</span>${
        keys.map(k => `<label><input type="radio" name="ry-metric" value="${k}" ${k === st.metric ? 'checked' : ''}>${METRICS[k].label}</label>`).join('')}</span>
      <span class="grp"><span class="grp-label">Years</span>${yearSelect('ry-a', D.meta.years, st.yearA)}<span>vs</span>${yearSelect('ry-b', D.meta.years, st.yearB)}</span>
      <span class="grp"><span class="grp-label">PIP</span>${seriesSelect('ry-pip', D.meta.pip_series, st.pip)}${
        D.series_filled ? `<select name="ry-basis">${Object.entries(BASES).map(([k, l]) => `<option value="${k}" ${k === st.basis ? 'selected' : ''}>${l}</option>`).join('')}</select>` : ''}</span>
      <span class="grp"><span class="grp-label">WID</span>${seriesSelect('ry-wid', D.meta.wid_series, st.wid)}</span>
      <span class="grp"><label title="PIP pairs only where both surveys use the same welfare concept (income or consumption)"><input type="checkbox" name="ry-welfare" ${st.sameWelfare ? 'checked' : ''}>same welfare</label></span>
      ${withMode ? `<span class="grp"><span class="grp-label">Change</span>
        <label><input type="radio" name="ry-mode" value="abs" ${st.mode === 'abs' ? 'checked' : ''}>Absolute</label>
        <label><input type="radio" name="ry-mode" value="rel" ${st.mode === 'rel' ? 'checked' : ''}>Relative (%)</label></span>` : ''}
    </div>`;
  }

  function wireControls(el, st, draw) {
    const on = (sel, fn) => el.querySelectorAll(sel).forEach(n => n.addEventListener('change', e => { fn(e.target); draw(); }));
    on('input[name=ry-metric]', t => { st.metric = t.value; });
    on('select[name=ry-a]', t => { st.yearA = +t.value; });
    on('select[name=ry-b]', t => { st.yearB = +t.value; });
    on('select[name=ry-pip]', t => { st.pip = t.value; });
    on('select[name=ry-wid]', t => { st.wid = t.value; });
    on('select[name=ry-basis]', t => { st.basis = t.value; });
    on('input[name=ry-welfare]', t => { st.sameWelfare = t.checked; });
    on('input[name=ry-mode]', t => { st.mode = t.value; });
  }

  function initState(D, props) {
    const keys = (props.metrics || Object.keys(METRICS)).filter(k => METRICS[k]);
    return {
      keys,
      metric: keys.includes(props.metric) ? props.metric : keys[0],
      yearA: D.meta.years.includes(+props.yearA) ? +props.yearA : 1993,
      yearB: D.meta.years.includes(+props.yearB) ? +props.yearB : 2019,
      pip: D.meta.pip_series.includes(props.pipSeries) ? props.pipSeries : 'PIP_topadj',
      wid: D.meta.wid_series.includes(props.widSeries) ? props.widSeries : 'WID_posttax_per_capita',
      sameWelfare: props.sameWelfare !== false,
      mode: props.mode === 'rel' ? 'rel' : 'abs',
      basis: props.basis === 'filled' && D.series_filled ? 'filled' : 'nearest_survey',
    };
  }

  function wireHover(svg, wrap, tip, tipHTML) {
    let active = null;
    const reset = () => { if (active) { active.setAttribute('r', active.dataset.baser || '5'); active = null; } };
    const over = e => { const c = e.target.closest && e.target.closest('.ry-dot'); if (!c || c === active) return;
      reset(); active = c; c.setAttribute('r', '8'); c.parentNode.appendChild(c);
      tip.innerHTML = tipHTML(c); Deck.placeTooltip(tip, c, wrap); tip.style.opacity = '1'; };
    const out = e => { const c = e.target.closest && e.target.closest('.ry-dot'); if (!c) return;
      const to = e.relatedTarget; if (to && to.closest && to.closest('.ry-dot')) return; reset(); tip.style.opacity = '0'; };
    const leave = () => { reset(); tip.style.opacity = '0'; };
    svg.addEventListener('mouseover', over); svg.addEventListener('mouseout', out); wrap.addEventListener('mouseleave', leave);
    return () => { svg.removeEventListener('mouseover', over); svg.removeEventListener('mouseout', out); wrap.removeEventListener('mouseleave', leave); };
  }

  function shell(el, D, st, props, viewBox, withMode) {
    el.innerHTML = STYLE + `
      <div class="ry-wrap">
        ${props.controls === false ? '' : controlsHTML(D, st, st.keys, withMode)}
        <div class="ry-plot"><svg class="ry-svg" viewBox="${viewBox}" preserveAspectRatio="xMidYMid meet"></svg></div>
        <div class="ry-legend"></div>
        <div class="ry-source">${props.source || SOURCE[st.basis]}</div>
        <div class="ry-tip"></div>
      </div>`;
  }

  /* ====================== year A vs year B, two panels ====================== */
  Deck.registerComponent('refyear-scatter', (el, props) => withData(el, (D) => {
    const st = initState(D, props);
    shell(el, D, st, props, '0 0 1200 500', false);
    const svg = el.querySelector('.ry-svg'), wrap = el.querySelector('.ry-wrap'), tip = el.querySelector('.ry-tip'),
      legend = el.querySelector('.ry-legend');
    // The chart title sits on its own line above the two panel titles.
    const PANEL = { y0: 68, y1: 430, w: 470, gap: 90, x0: 74, titleY: 48 };
    let last = { pip: [], wid: [] };

    function panel(rows, ox, series, dom) {
      const M = METRICS[st.metric];
      const px = v => ox + ((v - dom.lo) / (dom.hi - dom.lo)) * PANEL.w;
      const py = v => PANEL.y1 - ((v - dom.lo) / (dom.hi - dom.lo)) * (PANEL.y1 - PANEL.y0);
      let s = `<text x="${ox}" y="${PANEL.titleY}" class="ry-title">${D.meta.series[series]}</text>`
        + `<text x="${ox + PANEL.w}" y="${PANEL.titleY}" text-anchor="end" class="ry-sub">${rows.length} countries</text>`;
      dom.ticks.forEach(t => {
        if (t < dom.lo - 1e-9 || t > dom.hi + 1e-9) return;
        s += `<line class="ry-grid" x1="${ox}" x2="${ox + PANEL.w}" y1="${py(t)}" y2="${py(t)}"/>`
          + `<line class="ry-grid" x1="${px(t)}" x2="${px(t)}" y1="${PANEL.y0}" y2="${PANEL.y1}"/>`
          + `<text class="ry-tick" x="${ox - 8}" y="${py(t) + 4}" text-anchor="end">${M.tick(t)}</text>`
          + `<text class="ry-tick" x="${px(t)}" y="${PANEL.y1 + 20}" text-anchor="middle">${M.tick(t)}</text>`;
      });
      s += `<line class="ry-diag" x1="${px(dom.lo)}" y1="${py(dom.lo)}" x2="${px(dom.hi)}" y2="${py(dom.hi)}"/>`
        + `<text class="ry-note" x="${px(dom.hi) - 4}" y="${py(dom.hi) + 18}" text-anchor="end">no change</text>`
        + `<text class="ry-axis" x="${ox + PANEL.w / 2}" y="${PANEL.y1 + 42}" text-anchor="middle">${st.yearA}</text>`
        + `<text class="ry-axis" transform="translate(${ox - 44},${(PANEL.y0 + PANEL.y1) / 2}) rotate(-90)" text-anchor="middle">${st.yearB}</text>`;
      if (!rows.length) s += `<text class="ry-empty" x="${ox + PANEL.w / 2}" y="${(PANEL.y0 + PANEL.y1) / 2}" text-anchor="middle">no country has both years under these rules</text>`;
      rows.forEach((d, i) => {
        s += `<circle class="ry-dot" data-baser="5" data-side="${series === st.pip ? 'pip' : 'wid'}" data-i="${i}" `
          + `cx="${px(d.a)}" cy="${py(d.b)}" r="5" ${dotPaint(d, colorOf(d.r))}/>`;
      });
      return s;
    }

    function draw() {
      const M = METRICS[st.metric];
      const ia = D.meta.years.indexOf(st.yearA), ib = D.meta.years.indexOf(st.yearB);
      if (st.yearA === st.yearB) {
        svg.innerHTML = `<text class="ry-empty" x="600" y="250" text-anchor="middle">Pick two different years.</text>`;
        legend.innerHTML = ''; last = { pip: [], wid: [] }; return;
      }
      last = { pip: pairs(D, st.pip, st.metric, ia, ib, st.sameWelfare, st.basis), wid: pairs(D, st.wid, st.metric, ia, ib, false, st.basis) };
      if (!props.source) el.querySelector('.ry-source').textContent = SOURCE[st.basis];
      const all = last.pip.concat(last.wid).flatMap(d => [d.a, d.b]);
      const dom = axis(Math.min(...all), Math.max(...all), 5);
      svg.innerHTML =
        `<text x="600" y="18" text-anchor="middle" class="ry-title">${M.label} in ${st.yearA} vs ${st.yearB}</text>`
        + panel(last.pip, PANEL.x0, st.pip, dom)
        + panel(last.wid, PANEL.x0 + PANEL.w + PANEL.gap, st.wid, dom);
      legend.innerHTML = legendHTML(last.pip.concat(last.wid));
    }

    const cleanup = wireHover(svg, wrap, tip, c => {
      const d = last[c.dataset.side][+c.dataset.i], M = METRICS[st.metric];
      const ch = d.b - d.a; const arrow = ch > 0 ? '▲' : ch < 0 ? '▼' : '=';
      const src = c.dataset.side === 'pip' ? SHORT[st.pip] : SHORT[st.wid];
      return `<div><span class="sw" style="background:${colorOf(d.r)}"></span><b>${d.c}</b> <span style="opacity:.7">${src}</span></div>`
        + `<div class="r">${st.yearA}: ${M.val(d.a)}${surveyNote(d, 'a')}</div>`
        + `<div class="r">${st.yearB}: ${M.val(d.b)}${surveyNote(d, 'b')}</div>`
        + `<div class="r">${arrow} ${M.dch(Math.abs(ch))}</div>`;
    });
    wireControls(el, st, draw);
    draw();
    return cleanup;
  }));

  /* ====================== change in PIP vs change in WID ====================== */
  Deck.registerComponent('refyear-change-scatter', (el, props) => withData(el, (D) => {
    const st = initState(D, props);
    shell(el, D, st, props, '0 0 900 500', true);
    const svg = el.querySelector('.ry-svg'), wrap = el.querySelector('.ry-wrap'), tip = el.querySelector('.ry-tip'),
      legend = el.querySelector('.ry-legend');
    const P = { x0: 92, x1: 748, y0: 46, y1: 430 };
    let last = [];

    const change = (a, b) => st.mode === 'rel' ? (b - a) / a * 100 : (b - a);
    const fmt = x => st.mode === 'rel' ? (x >= 0 ? '+' : '') + x.toFixed(0) + '%'
      : (x >= 0 ? '+' : '') + METRICS[st.metric].dch(x);

    function rows() {
      const ia = D.meta.years.indexOf(st.yearA), ib = D.meta.years.indexOf(st.yearB);
      const wid = {}; pairs(D, st.wid, st.metric, ia, ib, false, st.basis).forEach(d => { wid[d.c] = d; });
      return pairs(D, st.pip, st.metric, ia, ib, st.sameWelfare, st.basis)
        .filter(d => wid[d.c] && (st.mode !== 'rel' || (d.a !== 0 && wid[d.c].a !== 0)))
        .map(d => ({ c: d.c, r: d.r, p: d, w: wid[d.c], ext: d.ext, x: change(d.a, d.b), y: change(wid[d.c].a, wid[d.c].b) }));
    }

    function draw() {
      const M = METRICS[st.metric];
      if (st.yearA === st.yearB) {
        svg.innerHTML = `<text class="ry-empty" x="450" y="250" text-anchor="middle">Pick two different years.</text>`;
        legend.innerHTML = ''; last = []; return;
      }
      last = rows();
      if (!props.source) el.querySelector('.ry-source').textContent = SOURCE[st.basis];
      const vals = last.flatMap(d => [d.x, d.y]);
      const mag = vals.length ? Math.max(Math.abs(Math.min(...vals)), Math.abs(Math.max(...vals))) : 1;
      const dom = axis(-mag, mag, 6), lo = dom.lo, hi = dom.hi;
      const px = v => P.x0 + ((v - lo) / (hi - lo)) * (P.x1 - P.x0);
      const py = v => P.y1 - ((v - lo) / (hi - lo)) * (P.y1 - P.y0);
      const tick = t => st.mode === 'rel' ? Math.round(t) + '%' : M.tick(t);
      const unit = st.mode === 'rel' ? ' (%)' : (st.metric === 'top10' || st.metric === 'top1' ? ' (pp)' : '');
      let s = `<text x="450" y="18" text-anchor="middle" class="ry-title">Change ${st.yearA}→${st.yearB}: ${SHORT[st.pip]} vs ${SHORT[st.wid]} — ${M.label} · ${st.mode === 'rel' ? 'relative' : 'absolute'} · ${last.length} countries</text>`;
      dom.ticks.forEach(t => {
        if (t < lo - 1e-9 || t > hi + 1e-9) return;
        s += `<line class="ry-grid" x1="${P.x0}" x2="${P.x1}" y1="${py(t)}" y2="${py(t)}"/>`
          + `<line class="ry-grid" x1="${px(t)}" x2="${px(t)}" y1="${P.y0}" y2="${P.y1}"/>`
          + `<text class="ry-tick" x="${P.x0 - 8}" y="${py(t) + 4}" text-anchor="end">${tick(t)}</text>`
          + `<text class="ry-tick" x="${px(t)}" y="${P.y1 + 20}" text-anchor="middle">${tick(t)}</text>`;
      });
      s += `<line class="ry-zero" x1="${px(0)}" x2="${px(0)}" y1="${P.y0}" y2="${P.y1}"/>`
        + `<line class="ry-zero" x1="${P.x0}" x2="${P.x1}" y1="${py(0)}" y2="${py(0)}"/>`
        + `<line class="ry-diag" x1="${px(lo)}" y1="${py(lo)}" x2="${px(hi)}" y2="${py(hi)}"/>`
        + `<text class="ry-note" x="${px(hi) - 4}" y="${py(hi) + 16}" text-anchor="end">sources agree</text>`
        + `<text class="ry-axis" x="${(P.x0 + P.x1) / 2}" y="${P.y1 + 42}" text-anchor="middle">Change in ${SHORT[st.pip]}${unit}</text>`
        + `<text class="ry-axis" transform="translate(${P.x0 - 52},${(P.y0 + P.y1) / 2}) rotate(-90)" text-anchor="middle">Change in ${SHORT[st.wid]}${unit}</text>`;
      if (!last.length) s += `<text class="ry-empty" x="${(P.x0 + P.x1) / 2}" y="${(P.y0 + P.y1) / 2}" text-anchor="middle">no country has both years in both sources under these rules</text>`;
      last.forEach((d, i) => {
        s += `<circle class="ry-dot" data-baser="5.5" data-i="${i}" cx="${px(d.x)}" cy="${py(d.y)}" r="5.5" `
          + `${dotPaint(d, colorOf(d.r))}/>`;
      });
      svg.innerHTML = s;
      legend.innerHTML = legendHTML(last);
    }

    const cleanup = wireHover(svg, wrap, tip, c => {
      const d = last[+c.dataset.i], M = METRICS[st.metric];
      return `<div><span class="sw" style="background:${colorOf(d.r)}"></span><b>${d.c}</b></div>`
        + `<div class="r">${SHORT[st.pip]}: ${M.val(d.p.a)} → ${M.val(d.p.b)} (${fmt(d.x)})${surveyNote(d.p, 'a')}${surveyNote(d.p, 'b')}</div>`
        + `<div class="r">${SHORT[st.wid]}: ${M.val(d.w.a)} → ${M.val(d.w.b)} (${fmt(d.y)})</div>`;
    });
    wireControls(el, st, draw);
    draw();
    return cleanup;
  }));
})();
