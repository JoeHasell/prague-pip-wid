/* fig-top1-share-scatter.js — top-1% income share, a PIP series vs WID post-tax.
 *
 * One bubble per country: x = the selected PIP-side series, y = WID post-tax.
 * The 45-degree line is agreement. A dropdown switches the PIP series so the
 * bridging steps can be flicked through on fixed axes.
 *
 * NO NUMBERS HERE — fetched from data/figures/fig_top1_share_scatter.json,
 * written by data/scripts/31_fig_top1_share_scatter.py.
 *
 * Props (all optional):
 *   src      data file
 *   series   which PIP series to show first (default meta.default_series)
 *   max      axis maximum in percent (default: rounded up from the data)
 */
Deck.registerComponent('fig-top1-share-scatter', (el, props, ctx) => {
  const SRC = props.src || 'data/figures/fig_top1_share_scatter.json';
  const PALETTE = ['#0072B2', '#E69F00', '#009E73', '#CC79A7',
                   '#56B4E9', '#D55E00', '#7A3E9D', '#444444'];
  const R_MIN = 2.6, R_MAX = 24;
  let dead = false, cleanup = null;
  el.innerHTML = `<div style="padding:24px;font:15px var(--font-body);color:rgb(140,155,175)">Loading…</div>`;
  fetch(SRC).then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${SRC}`); return r.json(); })
    .then(d => { if (!dead) cleanup = build(d); })
    .catch(e => { if (!dead) el.innerHTML =
      `<div style="padding:24px;font:14px var(--font-body);color:#b3261e">Could not load <code>${SRC}</code> — run ` +
      `<code>python data/scripts/31_fig_top1_share_scatter.py</code> (${e.message})</div>`; });
  return () => { dead = true; if (cleanup) cleanup(); };

  function build(D) {
    const keys = D.meta.series.map(s => s.key);
    let current = keys.includes(props.series) ? props.series : D.meta.default_series;
    // One fixed domain across every series, so switching does not rescale the plot.
    const all = D.countries.flatMap(c => [c.wid, ...keys.map(k => c.pip[k])]);
    const MAX = props.max ?? Math.ceil(Math.max(...all) / 10) * 10;
    const popMax = Math.max(...D.countries.map(c => c.pop));
    // H is constrained by the 720px stage: the wrap is full body width (1120),
    // so the rendered height is H x 1.12 and must clear the kicker.
    const W = 1000, H = 415, M = { top: 30, right: 340, bottom: 54, left: 74 };
    const plotW = W - M.left - M.right, plotH = H - M.top - M.bottom;
    const px = v => M.left + (v / MAX) * plotW;
    const py = v => M.top + plotH - (v / MAX) * plotH;
    const rOf = p => R_MIN + (R_MAX - R_MIN) * Math.sqrt(Math.max(p, 0) / popMax);
    const step = MAX <= 20 ? 5 : 10;
    const ticks = []; for (let t = 0; t <= MAX + 1e-9; t += step) ticks.push(t);

    el.innerHTML = `
      <style>
        .t1-wrap { position: relative; width: 100%; }
        .t1-ctl { display:flex; align-items:center; gap:9px; justify-content:flex-end;
          font:13px var(--font-body); color:var(--muted); margin-bottom:2px; }
        .t1-sel { font:13px var(--font-body); color:var(--ink); padding:3px 6px;
          border:1px solid var(--line); border-radius:4px; background:#fff; }
        .t1-svg { width:100%; height:auto; display:block; }
        .t1-grid { stroke: rgb(235,238,242); stroke-width:1; }
        .t1-diag { stroke: rgb(160,175,194); stroke-width:1.5; stroke-dasharray:5 4; }
        .t1-diaglab { font: italic 12px var(--font-body); fill: rgb(140,155,175); }
        .t1-tick { font:12.5px var(--font-body); fill: rgb(87,114,145); }
        .t1-axis { font:600 13.5px var(--font-body); fill: rgb(63,96,138); }
        .t1-dot { cursor:pointer; }
        .t1-leg { font:11.5px var(--font-body); fill: var(--ink); }
        .t1-legh { font:700 10.5px var(--font-body); fill: rgb(120,135,155);
          letter-spacing:.06em; text-transform:uppercase; }
        .t1-src { font:11.5px var(--font-body); fill: rgb(140,155,175); }
        .t1-tip { position:absolute; pointer-events:none; opacity:0; z-index:5;
          transform:translate(-50%,-100%); background:rgb(0,33,71); color:#fff;
          font:13px var(--font-body); padding:7px 10px; border-radius:6px;
          white-space:nowrap; box-shadow:0 6px 18px rgba(0,12,28,.35); transition:opacity .1s; }
        .t1-tip b { font-weight:700; } .t1-tip .r { color:rgba(255,255,255,.82); margin-top:3px; }
      </style>
      <div class="t1-wrap">
        <div class="t1-ctl"><label for="t1-sel">PIP series</label>
          <select id="t1-sel" class="t1-sel">${D.meta.series.map(s =>
            `<option value="${s.key}"${s.key === current ? ' selected' : ''}>${s.label}</option>`).join('')}</select></div>
        <svg class="t1-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"></svg>
        <div class="t1-tip"></div>
      </div>`;
    const svg = el.querySelector('.t1-svg'), tip = el.querySelector('.t1-tip');
    const wrap = el.querySelector('.t1-wrap'), sel = el.querySelector('#t1-sel');

    function draw() {
      const label = D.meta.series.find(s => s.key === current).label;
      const grid = ticks.map(t =>
        `<line x1="${px(t)}" x2="${px(t)}" y1="${M.top}" y2="${M.top + plotH}" class="t1-grid"/>` +
        `<line x1="${M.left}" x2="${M.left + plotW}" y1="${py(t)}" y2="${py(t)}" class="t1-grid"/>` +
        `<text x="${px(t)}" y="${M.top + plotH + 18}" text-anchor="middle" class="t1-tick">${t}%</text>` +
        `<text x="${M.left - 8}" y="${py(t) + 4}" text-anchor="end" class="t1-tick">${t}%</text>`).join('');
      const diag = `<line x1="${px(0)}" y1="${py(0)}" x2="${px(MAX)}" y2="${py(MAX)}" class="t1-diag"/>` +
        `<text x="${px(MAX) - 6}" y="${py(MAX) + 18}" text-anchor="end" class="t1-diaglab">the two agree</text>`;
      // largest populations first, so small countries stay clickable on top
      const order = [...D.countries].sort((a, b) => b.pop - a.pop);
      const dots = order.map((c, i) =>
        `<circle class="t1-dot" data-c="${encodeURIComponent(c.c)}" cx="${px(c.pip[current]).toFixed(1)}" ` +
        `cy="${py(c.wid).toFixed(1)}" r="${rOf(c.pop).toFixed(2)}" fill="${PALETTE[c.r % PALETTE.length]}" ` +
        `fill-opacity="0.62" stroke="#fff" stroke-width="1.1"/>`).join('');
      const rowH = 19, lx = M.left + plotW + 28;
      const legend = D.regions.map((r, i) =>
        `<circle cx="6" cy="${i * rowH}" r="5.5" fill="${PALETTE[i % PALETTE.length]}" stroke="#fff" stroke-width="1"/>` +
        `<text x="19" y="${i * rowH + 4}" class="t1-leg">${r}</text>`).join('');
      svg.innerHTML =
        grid + diag + dots +
        `<g transform="translate(${lx},${M.top + 14})"><text x="0" y="-14" class="t1-legh">Region</text>${legend}</g>` +
        `<text transform="translate(16,${M.top + plotH / 2}) rotate(-90)" text-anchor="middle" class="t1-axis">` +
        `Top 1% share &mdash; ${D.meta.wid_label}</text>` +
        `<text x="${M.left + plotW / 2}" y="${H - 22}" text-anchor="middle" class="t1-axis">Top 1% share &mdash; ${label}</text>` +
        `<text x="${M.left}" y="${H - 4}" class="t1-src">${D.meta.year}, ${D.meta.n_countries} countries. ` +
        `Bubble area &prop; population. Pipeline: ${D.meta.generated_by}</text>`;
    }
    function onOver(e) {
      const c = e.target.closest && e.target.closest('.t1-dot');
      if (!c) return;
      const rec = D.countries.find(x => x.c === decodeURIComponent(c.dataset.c));
      tip.innerHTML = `<div><b>${rec.c}</b></div>` +
        `<div class="r">${D.regions[rec.r]}</div>` +
        `<div class="r">PIP series: ${rec.pip[current].toFixed(1)}%</div>` +
        `<div class="r">WID post-tax: ${rec.wid.toFixed(1)}%</div>`;
      Deck.placeTooltip(tip, c, wrap);
      tip.style.opacity = '1';
    }
    const onOut = () => { tip.style.opacity = '0'; };
    const onChange = () => { current = sel.value; draw(); };
    svg.addEventListener('mouseover', onOver);
    wrap.addEventListener('mouseleave', onOut);
    sel.addEventListener('change', onChange);
    draw();
    return () => { svg.removeEventListener('mouseover', onOver);
      wrap.removeEventListener('mouseleave', onOut); sel.removeEventListener('change', onChange); };
  }
});
