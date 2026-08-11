/* fig-topadj-explainer.js — interactive explainer for the top-adjustment
 * step, showing the full PIP-side chain for a selectable country:
 *
 *   consumption (observed, blue)            — consumption countries only
 *     -> income basis (vermillion, dashed)  — the consumption→income step
 *       -> top-adjusted (purple)            — WID post-tax top shape grafted
 *                                             above P95, branching off at the
 *                                             splice line
 *
 * Colours deliberately match the consumption→income explainer slide
 * (consumption blue, income vermillion dashed); the top-adjusted series adds
 * purple. Two panels: full distribution + a zoom on the top where the graft
 * acts. Default country: Indonesia (consumption-based, so all three lines).
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_topadj_explainer.json,
 * produced by data/scripts/11_fig_topadj_explainer.py with the SAME
 * parameters as the bridging figure (splice P95, base = PIP_consinc).
 * Methods: consinc.py and topadj.py.
 *
 * Props (all optional):
 *   dataUrl   override the JSON path
 *   country   initial country (default from the JSON meta)
 */
Deck.registerComponent('fig-topadj-explainer', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_topadj_explainer.json';
  const CONS_C = '#0072B2';    // consumption (observed)
  const INCB_C = '#D55E00';    // income basis (imputed / observed)
  const ADJ_C = '#7A3E9D';     // top-adjusted

  el.innerHTML = `<div class="fte-loading">Loading figure data…</div>`;
  let dead = false, cleanupInner = null;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) cleanupInner = init(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="fte-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/11_fig_topadj_explainer.py</code> (${err.message})</div>`;
    });

  function init(data) {
    const countries = Object.keys(data.countries).sort();
    let current = (props.country && data.countries[props.country])
      ? props.country : data.meta.default_country;

    el.innerHTML = `
      <style>
        .fte-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
        .fte-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .fte-controls { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 0 8px 2px 0; }
        .fte-controls label { font: 600 13px var(--font-body); color: rgb(63,96,138); }
        .fte-select { font: 14px var(--font-body); color: var(--ink); padding: 3px 8px;
          border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 260px; }
        .fte-chart { position: relative; flex: 1; min-height: 0; }
        .fte-svg { width: 100%; height: 100%; display: block; }
        .fte-grid { stroke: rgb(238,241,245); stroke-width: 1; }
        .fte-tick { font: 12px var(--font-body); fill: rgb(87,114,145); }
        .fte-axis { font: 600 13px var(--font-body); fill: rgb(63,96,138); }
        .fte-ptitle { font: 700 14px var(--font-body); fill: var(--ink); }
        .fte-splice { stroke: rgb(150,163,180); stroke-width: 1.5; stroke-dasharray: 5 4; }
        .fte-splicelab { font: italic 11.5px var(--font-body); fill: rgb(120,135,155); }
        .fte-lab { font: 700 12.5px var(--font-body); }
        .fte-dot { cursor: pointer; }
        .fte-source { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
        .fte-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%, -100%); background: rgb(0,33,71); color: #fff;
          font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      </style>
      <div class="fte-wrap">
        <div class="fte-controls">
          <label for="fte-sel">Country</label>
          <select id="fte-sel" class="fte-select">
            ${countries.map(c => `<option${c === current ? ' selected' : ''}>${c}</option>`).join('')}
          </select>
        </div>
        <div class="fte-chart">
          <svg class="fte-svg" viewBox="0 0 1400 460" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="fte-tip"></div>
        </div>
      </div>`;

    const svg = el.querySelector('.fte-svg');
    const tip = el.querySelector('.fte-tip');
    const wrap = el.querySelector('.fte-chart');
    const sel = el.querySelector('#fte-sel');

    const mids = data.percentiles.mids;
    const labels = data.percentiles.labels;
    const aIdx = data.meta.anchor_index;
    const splice = data.meta.splice_percentile;

    const money = v => v >= 100 ? '$' + Math.round(v).toLocaleString()
      : v >= 10 ? '$' + v.toFixed(0)
      : v >= 1 ? '$' + (v % 1 === 0 ? v : v.toFixed(1)) : '$' + v.toFixed(2);

    function logTicks(lo, hi) {
      const t = [];
      for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
        for (const m of [1, 2, 5]) {
          const v = m * Math.pow(10, e);
          if (v >= lo * 0.999 && v <= hi * 1.001) t.push(v);
        }
      return t;
    }

    function draw(country) {
      const d = data.countries[country];
      const isCons = !!d.consinc;
      const base = isCons ? d.consinc : d.pip;              // the income basis
      const adjFull = base.slice(0, aIdx + 1).concat(d.adj); // full adjusted series

      // Series list: [values, colour, dash, label, drawFromAnchorOnly]
      const series = [];
      if (isCons) series.push({ vals: d.pip, color: CONS_C, dash: '', label: 'Consumption (observed)' });
      series.push({ vals: base, color: INCB_C, dash: '6 4',
                    label: isCons ? 'Income basis (imputed)' : 'Income (observed)' });
      series.push({ vals: adjFull, color: ADJ_C, dash: '', label: 'Top-adjusted', fromAnchor: true });

      const panels = [
        { x0: 74, x1: 750, pmin: 0, pmax: 100, title: 'Full distribution', filter: () => true },
        { x0: 856, x1: 1370, pmin: splice - 5, pmax: 100, title: `Zoom: the top ${100 - splice + 5}%`,
          filter: i => mids[i] >= splice - 5 },
      ];
      const yTop = 52, yBot = 396;

      let out = `<text x="16" y="20" class="fte-ptitle">${country}: the PIP-side chain — ` +
        `${isCons ? 'consumption → income basis → top-adjusted' : 'observed income → top-adjusted'}</text>`;
      const hover = [];

      // Chip legend, top right on the title line
      let lx = 1370 - series.reduce((w, s) => w + s.label.length * 6.6 + 38, 0);
      series.forEach(s => {
        out += `<line x1="${lx}" x2="${lx + 18}" y1="16" y2="16" stroke="${s.color}" stroke-width="3"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
        out += `<text x="${lx + 23}" y="20" class="fte-lab" fill="${s.color}" style="font-size:12px">${s.label}</text>`;
        lx += s.label.length * 6.6 + 38;
      });

      panels.forEach((p, pi) => {
        const idx = mids.map((m, i) => i).filter(p.filter);
        const vals = idx.flatMap(i => series.flatMap(s => s.vals[i])).filter(v => v > 0);
        const ticks = logTicks(Math.min(...vals), Math.max(...vals));
        const ylo = Math.log(Math.min(...vals)) - 0.08;
        const yhi = Math.log(Math.max(...vals)) + 0.08;
        const X = v => p.x0 + (v - p.pmin) / (p.pmax - p.pmin) * (p.x1 - p.x0);
        const Y = v => yBot - (Math.log(v) - ylo) / (yhi - ylo) * (yBot - yTop);

        out += `<text x="${p.x0}" y="${yTop - 14}" class="fte-ptitle" style="font-size:13px">${p.title}</text>`;
        out += ticks.map(t =>
          `<line x1="${p.x0}" x2="${p.x1}" y1="${Y(t)}" y2="${Y(t)}" class="fte-grid"/>` +
          `<text x="${p.x0 - 6}" y="${Y(t) + 4}" text-anchor="end" class="fte-tick">${money(t)}</text>`).join('');
        const xt = pi === 0 ? [0, 25, 50, 75, 100] : [90, 92, 94, 96, 98, 100];
        out += xt.filter(t => t >= p.pmin).map(t =>
          `<text x="${X(t)}" y="${yBot + 18}" text-anchor="middle" class="fte-tick">P${t}</text>`).join('');
        out += `<line x1="${X(splice)}" x2="${X(splice)}" y1="${yTop}" y2="${yBot}" class="fte-splice"/>`;
        if (pi === 1) out += `<text x="${X(splice) - 6}" y="${yTop + 12}" text-anchor="end" class="fte-splicelab">splice at P${splice}</text>`;

        const path = pts => 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L');
        series.forEach(s => {
          const sIdx = s.fromAnchor ? idx.filter(i => i >= aIdx) : idx;
          const pts = sIdx.map(i => [X(mids[i]), Y(s.vals[i])]);
          out += `<path d="${path(pts)}" fill="none" stroke="${s.color}" stroke-width="2.5"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
          if (pi === 1) {
            sIdx.forEach(i => {
              out += `<circle class="fte-dot" data-h="${hover.length}" cx="${X(mids[i])}" cy="${Y(s.vals[i])}" r="4" fill="${s.color}" stroke="#fff" stroke-width="1"/>`;
              hover.push({ t: `<b>${country}</b> ${labels[i]} — ${s.label}<br>${money(s.vals[i])}/month` });
            });
          }
        });
      });

      out += `<text transform="translate(16,${(yTop + yBot) / 2}) rotate(-90)" text-anchor="middle" class="fte-axis">Income per month (int-$, log scale)</text>`;
      out += `<text x="74" y="444" class="fte-source">2023, per capita. Income basis: consumption countries mapped via the dual-country regression (consinc.py). ` +
        `Top adjustment: WID post-tax shape above P${splice}, anchored at the p${splice - 1}–${splice} bin, applied on top (topadj.py). Chart data: data/figures/fig_topadj_explainer.json</text>`;

      svg.innerHTML = out;
      svg._hover = hover;
    }

    function onOver(e) {
      const dot = e.target.closest && e.target.closest('.fte-dot');
      if (!dot) return;
      const h = svg._hover[+dot.dataset.h];
      const cr = dot.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = (cr.left + cr.width / 2 - wr.left) + 'px';
      tip.style.top = (cr.top - wr.top - 6) + 'px';
      tip.innerHTML = h.t;
      tip.style.opacity = '1';
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.fte-dot')) return;
      tip.style.opacity = '0';
    }
    function onSel() { draw(sel.value); tip.style.opacity = '0'; }

    draw(current);
    sel.addEventListener('change', onSel);
    svg.addEventListener('mouseover', onOver);
    svg.addEventListener('mouseout', onOut);
    return () => {
      sel.removeEventListener('change', onSel);
      svg.removeEventListener('mouseover', onOver);
      svg.removeEventListener('mouseout', onOut);
    };
  }

  return () => { dead = true; if (cleanupInner) cleanupInner(); };
});
