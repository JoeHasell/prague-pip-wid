/* fig-consinc-explainer.js — interactive explainer for the consumption→income
 * adjustment: for a selectable consumption-based country, the PIP consumption
 * distribution with the regression-PREDICTED income distribution overlaid.
 * For dual countries (which also publish an actual income series for the
 * same year) the ACTUAL income line appears too — an in-sample fit check.
 * Default country: Albania (a dual one, so all three lines show).
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_consinc_explainer.json
 * (data/scripts/13_fig_consinc_explainer.py). The regression is defined in
 * data/scripts/04_fit_consinc.py; the series builder in consinc.py.
 *
 * Props (all optional):
 *   dataUrl   override the JSON path
 *   country   initial country (default from the JSON meta)
 */
Deck.registerComponent('fig-consinc-explainer', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_consinc_explainer.json';
  const CONS_C = '#0072B2';     // consumption (observed)
  const PRED_C = '#D55E00';     // predicted income (the model)
  const INC_C = '#009E73';      // actual income (dual countries only)

  el.innerHTML = `<div class="fce-loading">Loading figure data…</div>`;
  let dead = false, cleanupInner = null;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) cleanupInner = init(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="fce-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/13_fig_consinc_explainer.py</code> (${err.message})</div>`;
    });

  function init(data) {
    const countries = Object.keys(data.countries).sort();
    let current = (props.country && data.countries[props.country])
      ? props.country : data.meta.default_country;

    el.innerHTML = `
      <style>
        .fce-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
        .fce-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .fce-controls { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 0 8px 2px 0; }
        .fce-controls label { font: 600 13px var(--font-body); color: rgb(63,96,138); }
        .fce-select { font: 14px var(--font-body); color: var(--ink); padding: 3px 8px;
          border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 280px; }
        .fce-chart { position: relative; flex: 1; min-height: 0; }
        .fce-svg { width: 100%; height: 100%; display: block; }
        .fce-grid { stroke: rgb(238,241,245); stroke-width: 1; }
        .fce-tick { font: 12px var(--font-body); fill: rgb(87,114,145); }
        .fce-axis { font: 600 13px var(--font-body); fill: rgb(63,96,138); }
        .fce-ptitle { font: 700 15px var(--font-body); fill: var(--ink); }
        .fce-lab { font: 700 13px var(--font-body); }
        .fce-note { font: italic 12.5px var(--font-body); fill: rgb(100,118,140); }
        .fce-source { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
        .fce-pt { cursor: pointer; }
        .fce-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%, -100%); background: rgb(0,33,71); color: #fff;
          font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      </style>
      <div class="fce-wrap">
        <div class="fce-controls">
          <label for="fce-sel">Country</label>
          <select id="fce-sel" class="fce-select">
            ${countries.map(c => {
              const dual = !!data.countries[c].inc;
              return `<option value="${c}"${c === current ? ' selected' : ''}>${c}${dual ? ' *' : ''}</option>`;
            }).join('')}
          </select>
        </div>
        <div class="fce-chart">
          <svg class="fce-svg" viewBox="0 0 1400 470" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="fce-tip"></div>
        </div>
      </div>`;

    const svg = el.querySelector('.fce-svg');
    const tip = el.querySelector('.fce-tip');
    const wrap = el.querySelector('.fce-chart');
    const sel = el.querySelector('#fce-sel');

    const money = v => v >= 100 ? '$' + Math.round(v).toLocaleString()
      : v >= 10 ? '$' + v.toFixed(0)
      : v >= 1 ? '$' + (v % 1 === 0 ? v : v.toFixed(1)) : '$' + v.toFixed(2);

    function draw(country) {
      const d = data.countries[country];
      const X0 = 76, X1 = 1360, yTop = 54, yBot = 396;
      const series = [
        { key: 'cons', vals: d.cons, color: CONS_C, dash: '', label: 'Consumption (observed)' },
        { key: 'pred', vals: d.pred, color: PRED_C, dash: '6 4', label: 'Income (predicted)' },
      ];
      if (d.inc) series.push(
        { key: 'inc', vals: d.inc, color: INC_C, dash: '', label: 'Income (actual)' });

      const all = series.flatMap(s => s.vals).filter(v => v > 0);
      const lo = Math.pow(10, Math.floor(Math.log10(Math.min(...all))));
      const hiRaw = Math.max(...all);
      let hi = Math.pow(10, Math.ceil(Math.log10(hiRaw)));
      if (hi / hiRaw > 2) hi /= 2;
      const X = p => X0 + (p - 0.5) / 100 * (X1 - X0);
      const Y = v => yBot - (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo)) * (yBot - yTop);
      const TICKS = [];
      for (let e = Math.floor(Math.log10(lo)); e <= Math.ceil(Math.log10(hi)); e++)
        for (const m of [1, 2, 5]) {
          const t = m * Math.pow(10, e);
          if (t >= lo * 0.999 && t <= hi * 1.001) TICKS.push(t);
        }

      const hover = [];
      let out = `<text x="${X0}" y="22" class="fce-ptitle">${country}, ${d.year}: consumption vs ${d.inc ? 'predicted and actual income' : 'predicted income'}</text>`;
      out += TICKS.map(t =>
        `<line x1="${X0}" x2="${X1}" y1="${Y(t)}" y2="${Y(t)}" class="fce-grid"/>` +
        `<text x="${X0 - 8}" y="${Y(t) + 4}" text-anchor="end" class="fce-tick">${money(t)}</text>`).join('');
      out += [1, 25, 50, 75, 100].map(p =>
        `<text x="${X(p)}" y="${yBot + 20}" text-anchor="middle" class="fce-tick">P${p}</text>`).join('');

      const path = vals => 'M' + vals.map((v, i) =>
        `${X(i + 1).toFixed(1)},${Y(v).toFixed(1)}`).join('L');
      series.forEach(s => {
        out += `<path d="${path(s.vals)}" fill="none" stroke="${s.color}" stroke-width="2.5"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
        // decile dots for hover
        for (let p = 10; p <= 100; p += 10) {
          const v = s.vals[p - 1];
          out += `<circle class="fce-pt" data-h="${hover.length}" cx="${X(p)}" cy="${Y(v)}" r="4" fill="${s.color}" stroke="#fff" stroke-width="1"/>`;
          hover.push({ t: `<b>${country}</b> p${p} — ${s.label}<br>${money(v)}/month` });
        }
      });

      // Chip legend (top right) — end-of-line labels collide with the
      // steep tails, chips don't.
      let lx = X1 - series.reduce((w, s) => w + s.label.length * 7 + 40, 0);
      series.forEach(s => {
        out += `<line x1="${lx}" x2="${lx + 20}" y1="${yTop - 12}" y2="${yTop - 12}" stroke="${s.color}" stroke-width="3"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
        out += `<text x="${lx + 26}" y="${yTop - 8}" class="fce-lab" fill="${s.color}" style="font-size:12.5px">${s.label}</text>`;
        lx += s.label.length * 7 + 40;
      });

      if (!d.inc) out += `<text x="${X0}" y="${yTop - 8}" class="fce-note">No actual income series for this country — the prediction is an out-of-sample transfer.</text>`;
      out += `<text transform="translate(16,${(yTop + yBot) / 2}) rotate(-90)" text-anchor="middle" class="fce-axis">Income / consumption per month (int-$, log scale)</text>`;
      out += `<text x="${X0}" y="448" class="fce-source">PIP percentile bin averages, 2021 PPPs, most recent national consumption year. Prediction: ln y&#8346; = &alpha;&#8346; + &beta;&#8346; ln c&#8346;, fitted on 88 dual country-years (data/scripts/04_fit_consinc.py). * in the dropdown = actual income available.</text>`;

      svg.innerHTML = out;
      svg._hover = hover;
    }

    function onOver(e) {
      const pt = e.target.closest && e.target.closest('.fce-pt');
      if (!pt) return;
      const h = svg._hover[+pt.dataset.h];
      const cr = pt.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = (cr.left + cr.width / 2 - wr.left) + 'px';
      tip.style.top = (cr.top - wr.top - 6) + 'px';
      tip.innerHTML = h.t;
      tip.style.opacity = '1';
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.fce-pt')) return;
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
