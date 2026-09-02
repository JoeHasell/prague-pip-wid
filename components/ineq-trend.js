/* ineq-trend.js — two interactive charts on how inequality changed 1993->2019.
 *
 * Registers TWO components sharing one embedded dataset:
 *   ineq-trend-scatter  : slide 7 — two panels (PIP | WID), each a scatter of
 *                         a country's inequality in 1993 (x) vs 2019 (y).
 *                         45-deg line = no change; above = rose. Radio toggles
 *                         the metric (Gini / Top 10% share / Palma).
 *   ineq-change-scatter : slide 8 — one scatter of the CHANGE in PIP inequality
 *                         (x) vs the change in WID inequality (y). Radios toggle
 *                         the metric and absolute vs relative change.
 *
 * Data: World Bank PIP (disposable, per capita) and WID.world (pre-tax national,
 * per adult), reference years 1993 & 2019, via Our World in Data. Colours: World
 * Bank PIP regions (Okabe-Ito, colourblind-safe).
 */
(function () {
  // Data is fetched, not embedded: data/figures/fig_ineq_trend.json, written by
  // data/scripts/25_fig_scatters_from_etl.py from OWID's ETL. Both components
  // share one request.
  const DATA_URL = 'data/figures/fig_ineq_trend.json';
  let dataPromise = null;
  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch(DATA_URL)
        .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
        .then(json => json.countries);
    }
    return dataPromise;
  }
  // Renders `build(DATA)` once the data is in, and forwards its cleanup.
  function withData(el, build) {
    el.innerHTML = `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">Loading figure data…</div>`;
    let dead = false;
    let inner = null;
    loadData()
      .then(DATA => { if (!dead) inner = build(DATA); })
      .catch(err => {
        if (!dead) el.innerHTML =
          `<div style="padding:32px;font:15px var(--font-body);color:rgb(120,135,155)">` +
          `Could not load ${DATA_URL} — run ` +
          `<code>python data/scripts/25_fig_scatters_from_etl.py</code> (${err.message})</div>`;
      });
    return () => { dead = true; if (inner) inner(); };
  }


  const METRICS = {
    gini:  { label: 'Gini',          tick: v => v.toFixed(2),           val: v => v.toFixed(3),        unit: '' },
    top10: { label: 'Top 10% share', tick: v => Math.round(v) + '%',    val: v => v.toFixed(1) + '%',  unit: 'pp' },
    top1:  { label: 'Top 1% share',  tick: v => Math.round(v) + '%',    val: v => v.toFixed(1) + '%',  unit: 'pp' },
    palma: { label: 'Palma ratio',   tick: v => v.toFixed(1),           val: v => v.toFixed(2),        unit: '' },
  };
  const REGIONS = ['Sub-Saharan Africa', 'Other high income countries', 'Europe and Central Asia',
    'East Asia and Pacific', 'Middle East and North Africa', 'South Asia', 'Latin America and the Caribbean'];
  const PALETTE = ['#0072B2', '#E69F00', '#009E73', '#CC79A7', '#56B4E9', '#D55E00', '#7A3E9D'];
  const colorOf = r => PALETTE[Math.max(0, REGIONS.indexOf(r)) % PALETTE.length];

  function niceNum(x, round) {
    const exp = Math.floor(Math.log10(x)); const f = x / Math.pow(10, exp);
    let nf; if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10;
    else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return nf * Math.pow(10, exp);
  }
  function axis(lo, hi, n) {
    if (hi === lo) { hi = lo + 1; }
    const range = niceNum(hi - lo, false);
    const step = niceNum(range / Math.max(1, n - 1), true);
    const glo = Math.floor(lo / step) * step, ghi = Math.ceil(hi / step) * step;
    const ticks = []; for (let v = glo; v <= ghi + step * 0.5; v += step) ticks.push(Math.round(v / step) * step);
    return { ticks, lo: glo, hi: ghi };
  }

  const STYLE = `
    <style>
      .iq-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
      .iq-controls { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; padding: 2px 4px 8px; font: 14px var(--font-body); color: var(--ink); }
      .iq-controls .grp { display: flex; gap: 12px; align-items: center; }
      .iq-controls .grp-label { font: 700 11px var(--font-body); letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
      .iq-controls label { display: inline-flex; gap: 5px; align-items: center; cursor: pointer; }
      .iq-controls input { accent-color: var(--accent); cursor: pointer; }
      .iq-plot { flex: 1; min-height: 0; }
      .iq-svg { width: 100%; height: 100%; display: block; }
      .iq-title { font: 700 16px var(--font-body); fill: var(--ink); }
      .iq-grid { stroke: rgb(235, 238, 242); stroke-width: 1; }
      .iq-tick { font: 12px var(--font-body); fill: rgb(87, 114, 145); }
      .iq-axis { font: 600 13px var(--font-body); fill: rgb(63, 96, 138); }
      .iq-diag { stroke: rgb(160, 175, 194); stroke-width: 1.5; stroke-dasharray: 5 4; }
      .iq-zero { stroke: rgb(120, 140, 165); stroke-width: 1; }
      .iq-note { font: italic 11px var(--font-body); fill: rgb(140, 155, 175); }
      .iq-dot { cursor: pointer; transition: r 0.08s ease; }
      .iq-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 8px 4px 0; font: 12px var(--font-body); color: var(--ink); }
      .iq-legend span.k { display: inline-flex; gap: 6px; align-items: center; }
      .iq-legend i { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
      .iq-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0; transform: translate(-50%, -100%);
        background: rgb(0, 33, 71); color: #fff; font: 13px var(--font-body); padding: 8px 11px; border-radius: 6px;
        white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      .iq-tip b { font-weight: 700; } .iq-tip .r { color: rgba(255,255,255,0.82); margin-top: 3px; }
      .iq-tip .sw { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
    </style>`;

  function legendHTML(regionsPresent) {
    return `<div class="iq-legend">` + regionsPresent.map(r =>
      `<span class="k"><i style="background:${colorOf(r)}"></i>${r}</span>`).join('') + `</div>`;
  }
  function regionsIn(rows) { return REGIONS.filter(r => rows.some(d => d.r === r)); }

  // Shared hover wiring: delegated over the svg, catch-all on the wrapper.
  function wireHover(svg, wrap, tip, tipHTML) {
    let active = null;
    const reset = () => { if (active) { active.setAttribute('r', active.dataset.baser || '5'); active = null; } };
    const over = e => { const c = e.target.closest && e.target.closest('.iq-dot'); if (!c || c === active) return;
      reset(); active = c; c.setAttribute('r', '8'); c.parentNode.appendChild(c);
      const cr = c.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = (cr.left + cr.width / 2 - wr.left) + 'px'; tip.style.top = (cr.top - wr.top - 6) + 'px';
      tip.innerHTML = tipHTML(c); tip.style.opacity = '1'; };
    const out = e => { const c = e.target.closest && e.target.closest('.iq-dot'); if (!c) return;
      const to = e.relatedTarget; if (to && to.closest && to.closest('.iq-dot')) return; reset(); tip.style.opacity = '0'; };
    const leave = () => { reset(); tip.style.opacity = '0'; };
    svg.addEventListener('mouseover', over); svg.addEventListener('mouseout', out); wrap.addEventListener('mouseleave', leave);
    return () => { svg.removeEventListener('mouseover', over); svg.removeEventListener('mouseout', out); wrap.removeEventListener('mouseleave', leave); };
  }

  /* ============================ SLIDE 7 ============================ */
  Deck.registerComponent('ineq-trend-scatter', (el, props) => withData(el, (DATA) => {
    const keys = props.metrics || ['gini', 'top10', 'palma'];
    let metric = props.metric || keys[0];

    el.innerHTML = STYLE + `
      <div class="iq-wrap">
        <div class="iq-controls"><span class="grp-label">Metric</span><span class="grp">${
          keys.map(k => `<label><input type="radio" name="trm" value="${k}" ${k === metric ? 'checked' : ''}>${METRICS[k].label}</label>`).join('')
        }</span></div>
        <div class="iq-plot"><svg class="iq-svg" viewBox="0 0 1200 500" preserveAspectRatio="xMidYMid meet"></svg></div>
        ${legendHTML(regionsIn(DATA))}
        <div class="iq-tip"></div>
      </div>`;

    const svg = el.querySelector('.iq-svg'), wrap = el.querySelector('.iq-wrap'), tip = el.querySelector('.iq-tip');
    const PANEL = { y0: 54, y1: 430, w: 470, gap: 90, x0: 74 };

    function panel(rows, ox, mkey, srcLabel, dom) {
      const M = METRICS[mkey];
      const px = v => ox + ((v - dom.lo) / (dom.hi - dom.lo)) * PANEL.w;
      const py = v => PANEL.y1 - ((v - dom.lo) / (dom.hi - dom.lo)) * (PANEL.y1 - PANEL.y0);
      let s = `<text x="${ox}" y="34" class="iq-title">${srcLabel}</text>`;
      dom.ticks.forEach(t => {
        if (t < dom.lo - 1e-9 || t > dom.hi + 1e-9) return;
        s += `<line class="iq-grid" x1="${ox}" x2="${ox + PANEL.w}" y1="${py(t)}" y2="${py(t)}"/>`
          + `<line class="iq-grid" x1="${px(t)}" x2="${px(t)}" y1="${PANEL.y0}" y2="${PANEL.y1}"/>`
          + `<text class="iq-tick" x="${ox - 8}" y="${py(t) + 4}" text-anchor="end">${M.tick(t)}</text>`
          + `<text class="iq-tick" x="${px(t)}" y="${PANEL.y1 + 20}" text-anchor="middle">${M.tick(t)}</text>`;
      });
      s += `<line class="iq-diag" x1="${px(dom.lo)}" y1="${py(dom.lo)}" x2="${px(dom.hi)}" y2="${py(dom.hi)}"/>`
        + `<text class="iq-note" x="${px(dom.hi) - 4}" y="${py(dom.hi) + 18}" text-anchor="end">no change</text>`;
      s += `<text class="iq-axis" x="${ox + PANEL.w / 2}" y="${PANEL.y1 + 42}" text-anchor="middle">1993</text>`;
      s += `<text class="iq-axis" transform="translate(${ox - 44},${(PANEL.y0 + PANEL.y1) / 2}) rotate(-90)" text-anchor="middle">2019</text>`;
      rows.forEach(d => {
        s += `<circle class="iq-dot" data-baser="5" data-c="${encodeURIComponent(d.c)}" data-m="${mkey}" data-src="${srcLabel}" `
          + `cx="${px(d.a)}" cy="${py(d.b)}" r="5" fill="${colorOf(d.r)}" fill-opacity="0.82" stroke="#fff" stroke-width="1.2"/>`;
      });
      return s;
    }

    function draw() {
      const M = METRICS[metric];
      const pipRows = DATA.filter(d => d[metric + '_pip93'] != null && d[metric + '_pip19'] != null)
        .map(d => ({ c: d.c, r: d.r, a: d[metric + '_pip93'], b: d[metric + '_pip19'] }));
      const widRows = DATA.filter(d => d[metric + '_wid93'] != null && d[metric + '_wid19'] != null)
        .map(d => ({ c: d.c, r: d.r, a: d[metric + '_wid93'], b: d[metric + '_wid19'] }));
      const all = pipRows.concat(widRows).flatMap(d => [d.a, d.b]);
      const dom = axis(Math.min(...all), Math.max(...all), 5);
      svg.innerHTML =
        `<text x="600" y="18" text-anchor="middle" class="iq-title">Inequality in 1993 vs 2019 — ${M.label}  ·  ${pipRows.length} PIP, ${widRows.length} WID countries</text>`
        + panel(pipRows, PANEL.x0, metric, 'World Bank PIP', dom)
        + panel(widRows, PANEL.x0 + PANEL.w + PANEL.gap, metric, 'WID (pre-tax)', dom);
    }

    const cleanup = wireHover(svg, wrap, tip, c => {
      const name = decodeURIComponent(c.dataset.c), mkey = c.dataset.m;
      const d = DATA.find(x => x.c === name); const src = c.dataset.src.indexOf('PIP') >= 0 ? 'pip' : 'wid';
      const v93 = d[mkey + '_' + src + '93'], v19 = d[mkey + '_' + src + '19'], M = METRICS[mkey];
      const ch = v19 - v93; const arrow = ch > 0 ? '▲' : ch < 0 ? '▼' : '=';
      return `<div><span class="sw" style="background:${colorOf(d.r)}"></span><b>${d.c}</b> <span style="opacity:.7">${c.dataset.src}</span></div>`
        + `<div class="r">1993: ${M.val(v93)}</div><div class="r">2019: ${M.val(v19)}</div>`
        + `<div class="r">${arrow} ${M.val(Math.abs(ch))} change</div>`;
    });

    el.querySelectorAll('input[name=trm]').forEach(r => r.addEventListener('change', e => { metric = e.target.value; draw(); }));
    draw();
    return cleanup;
  }));

  /* ============================ SLIDE 8 ============================ */
  Deck.registerComponent('ineq-change-scatter', (el, props) => withData(el, (DATA) => {
    const keys = props.metrics || ['gini', 'top10', 'palma'];
    let metric = props.metric || keys[0];
    let mode = props.mode || 'abs'; // 'abs' or 'rel'

    el.innerHTML = STYLE + `
      <div class="iq-wrap">
        <div class="iq-controls">
          <span class="grp-label">Metric</span><span class="grp">${
            keys.map(k => `<label><input type="radio" name="chm" value="${k}" ${k === metric ? 'checked' : ''}>${METRICS[k].label}</label>`).join('')}</span>
          <span class="grp-label" style="margin-left:14px">Change</span><span class="grp">
            <label><input type="radio" name="chmode" value="abs" ${mode === 'abs' ? 'checked' : ''}>Absolute</label>
            <label><input type="radio" name="chmode" value="rel" ${mode === 'rel' ? 'checked' : ''}>Relative (%)</label></span>
        </div>
        <div class="iq-plot"><svg class="iq-svg" viewBox="0 0 900 500" preserveAspectRatio="xMidYMid meet"></svg></div>
        ${legendHTML(regionsIn(DATA))}
        <div class="iq-tip"></div>
      </div>`;

    const svg = el.querySelector('.iq-svg'), wrap = el.querySelector('.iq-wrap'), tip = el.querySelector('.iq-tip');
    const P = { x0: 92, x1: 748, y0: 46, y1: 430 };

    function change(v93, v19) { return mode === 'rel' ? (v19 - v93) / v93 * 100 : (v19 - v93); }
    function fmtChange(x) { return mode === 'rel' ? (x >= 0 ? '+' : '') + x.toFixed(0) + '%' : (x >= 0 ? '+' : '') + x.toFixed(mode === 'abs' && metric === 'top10' ? 1 : 2); }

    function rows() {
      return DATA.filter(d => ['pip93', 'pip19', 'wid93', 'wid19'].every(k => d[metric + '_' + k] != null))
        .map(d => ({ c: d.c, r: d.r, x: change(d[metric + '_pip93'], d[metric + '_pip19']), y: change(d[metric + '_wid93'], d[metric + '_wid19']) }));
    }

    function draw() {
      const M = METRICS[metric]; const rs = rows();
      const vals = rs.flatMap(d => [d.x, d.y]); const mag = Math.max(Math.abs(Math.min(...vals)), Math.abs(Math.max(...vals)));
      const dom = axis(-mag, mag, 6);
      const lo = dom.lo, hi = dom.hi;
      const px = v => P.x0 + ((v - lo) / (hi - lo)) * (P.x1 - P.x0);
      const py = v => P.y1 - ((v - lo) / (hi - lo)) * (P.y1 - P.y0);
      const unit = mode === 'rel' ? ' (%)' : (metric === 'top10' ? ' (pp)' : '');
      let s = `<text x="450" y="18" text-anchor="middle" class="iq-title">Change 1993→2019: PIP vs WID — ${M.label} · ${mode === 'rel' ? 'relative' : 'absolute'} · ${rs.length} countries</text>`;
      dom.ticks.forEach(t => {
        if (t < lo - 1e-9 || t > hi + 1e-9) return;
        s += `<line class="iq-grid" x1="${P.x0}" x2="${P.x1}" y1="${py(t)}" y2="${py(t)}"/>`
          + `<line class="iq-grid" x1="${px(t)}" x2="${px(t)}" y1="${P.y0}" y2="${P.y1}"/>`
          + `<text class="iq-tick" x="${P.x0 - 8}" y="${py(t) + 4}" text-anchor="end">${mode === 'rel' ? Math.round(t) + '%' : t.toFixed(2)}</text>`
          + `<text class="iq-tick" x="${px(t)}" y="${P.y1 + 20}" text-anchor="middle">${mode === 'rel' ? Math.round(t) + '%' : t.toFixed(2)}</text>`;
      });
      // zero lines (rose vs fell) and 45-degree agreement line
      s += `<line class="iq-zero" x1="${px(0)}" x2="${px(0)}" y1="${P.y0}" y2="${P.y1}"/>`
        + `<line class="iq-zero" x1="${P.x0}" x2="${P.x1}" y1="${py(0)}" y2="${py(0)}"/>`
        + `<line class="iq-diag" x1="${px(lo)}" y1="${py(lo)}" x2="${px(hi)}" y2="${py(hi)}"/>`
        + `<text class="iq-note" x="${px(hi) - 4}" y="${py(hi) + 16}" text-anchor="end">sources agree</text>`;
      s += `<text class="iq-axis" x="${(P.x0 + P.x1) / 2}" y="${P.y1 + 42}" text-anchor="middle">Change in PIP inequality${unit}</text>`
        + `<text class="iq-axis" transform="translate(${P.x0 - 52},${(P.y0 + P.y1) / 2}) rotate(-90)" text-anchor="middle">Change in WID inequality${unit}</text>`;
      rs.forEach(d => {
        s += `<circle class="iq-dot" data-baser="5.5" data-c="${encodeURIComponent(d.c)}" cx="${px(d.x)}" cy="${py(d.y)}" r="5.5" `
          + `fill="${colorOf(d.r)}" fill-opacity="0.82" stroke="#fff" stroke-width="1.2"/>`;
      });
      svg.innerHTML = s;
    }

    const cleanup = wireHover(svg, wrap, tip, c => {
      const name = decodeURIComponent(c.dataset.c), d = DATA.find(x => x.c === name), M = METRICS[metric];
      const xp = change(d[metric + '_pip93'], d[metric + '_pip19']), yp = change(d[metric + '_wid93'], d[metric + '_wid19']);
      return `<div><span class="sw" style="background:${colorOf(d.r)}"></span><b>${d.c}</b></div>`
        + `<div class="r">PIP change: ${fmtChange(xp)}</div><div class="r">WID change: ${fmtChange(yp)}</div>`;
    });

    el.querySelectorAll('input[name=chm]').forEach(r => r.addEventListener('change', e => { metric = e.target.value; draw(); }));
    el.querySelectorAll('input[name=chmode]').forEach(r => r.addEventListener('change', e => { mode = e.target.value; draw(); }));
    draw();
    return cleanup;
  }));
})();
