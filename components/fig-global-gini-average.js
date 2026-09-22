/* fig-global-gini-average.js — the average country Gini across the world, 1990-2024.
 *
 * One line per series: the mean of the country Ginis at each reference year, for PIP as
 * published, PIP's two adjusted chains (WID profile, solid; Wollburg et al. inverse, dashed)
 * and WID pre-tax / post-tax per capita. Selectors switch between the unweighted and the
 * population-weighted average, and between four country samples. Lines are labelled at
 * their right end; a shared hover reads every series, and the sample's coverage, for the
 * year under the pointer. This is an average of within-country inequality, not the Gini
 * of the world distribution.
 *
 * DATA IS NOT EMBEDDED. Fetches
 *     data/figures/fig_global_gini_average.json
 * produced by data/scripts/36_global_gini_averages.py from
 * data/processed/reference_year_indicators.csv (33_).
 *
 * Props (all optional):
 *   dataUrl    override the JSON path
 *   title      chart title; pass "" to omit it
 *   weighting  starting weighting: unweighted | weighted
 *   sample     starting sample: common | balanced | own | common_ex_ci
 *   sources    ordered array of series keys to draw (default: all seven)
 *   controls   false hides both selectors (a fixed talk slide)
 *   height     viewBox height (default 540)
 */
(function () {
  const DEFAULT_URL = 'data/figures/fig_global_gini_average.json';

  // PIP side warm, WID side cool, as on fig-between-share-trend. The Wollburg chain
  // shares its WID-profile twin's colour and is drawn dashed.
  const COLOR = {
    PIP: '#D55E00',
    PIP_consinc: '#E69F00',
    PIP_topadj: '#B4761A',
    PIP_consinc_wb: '#E69F00',
    PIP_topadj_wb: '#B4761A',
    WID_pretax_per_capita: '#0072B2',
    WID_posttax_per_capita: '#009E73',
  };
  const DASHED = new Set(['PIP_consinc_wb', 'PIP_topadj_wb']);
  const CHROME = { grid: 'rgb(238,241,245)', tick: 'rgb(87,114,145)', axis: 'rgb(63,96,138)', faint: 'rgb(140,155,175)' };

  function styles(p) {
    return `
      .${p}-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
      .${p}-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
      .${p}-title { font: 700 19px var(--font-body); color: var(--ink); padding: 0 4px 4px 2px; }
      .${p}-controls { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 0 8px 2px 0; }
      .${p}-controls label { font: 600 13px var(--font-body); color: ${CHROME.axis}; }
      .${p}-select { font: 14px var(--font-body); color: var(--ink); padding: 3px 8px;
        border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 340px; }
      .${p}-note { font: italic 12px var(--font-body); color: rgb(120,135,155); padding: 1px 8px 0 2px; text-align: right; }
      .${p}-chart { position: relative; flex: 1; min-height: 0; }
      .${p}-svg { width: 100%; height: 100%; display: block; }
      .${p}-grid { stroke: ${CHROME.grid}; stroke-width: 1; }
      .${p}-tick { font: 12px var(--font-body); fill: ${CHROME.tick}; }
      .${p}-axis { font: 600 13px var(--font-body); fill: ${CHROME.axis}; }
      .${p}-label { font: 700 12.5px var(--font-body); }
      .${p}-shade { fill: rgb(0,33,71); fill-opacity: 0.045; }
      .${p}-shadelabel { font: italic 11.5px var(--font-body); fill: ${CHROME.faint}; }
      .${p}-hover { stroke: rgb(120,135,155); stroke-width: 1; stroke-dasharray: 3 3; }
      .${p}-source { font: 11.5px var(--font-body); fill: ${CHROME.faint}; }
      .${p}-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
        background: rgb(0,33,71); color: #fff;
        font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px;
        white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; line-height: 1.35; }
      .${p}-tip b { font-weight: 700; }
      .${p}-tip .sw { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
    `;
  }

  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');

  function yearTicks(years) {
    const out = years.filter(y => y % 5 === 0);
    if (!out.includes(years[0])) out.unshift(years[0]);
    if (!out.includes(years[years.length - 1])) out.push(years[years.length - 1]);
    return out;
  }

  function niceTicks(lo, hi, n) {
    const span = hi - lo;
    if (span <= 0) return [lo];
    const raw = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }


  // Keep the readout INSIDE the plot: beside the hover line, flipped when it would
  // overflow to the right, clamped vertically. Anchoring it above the plot's top edge
  // put it behind the slide title, where the card's clip cut off half its rows.
  function placeTip(svg, tip, plot, anchorX, pointerY) {
    const box = svg.getBoundingClientRect();
    const vb = svg.viewBox.baseVal;
    // preserveAspectRatio="xMidYMid meet": the drawing is letterboxed in whichever
    // dimension is not constraining, so both the scale and the offsets matter.
    const k = Math.min(box.width / vb.width, box.height / vb.height);
    const ox = (box.width - vb.width * k) / 2;
    const oy = (box.height - vb.height * k) / 2;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    const px = ox + anchorX * k;
    const plotL = ox + plot.x0 * k, plotR = ox + plot.x1 * k;
    let x = px + 14;
    if (x + tw > plotR - 4) x = px - 14 - tw;
    const loY = oy + plot.y0 * k + 4;
    const hiY = Math.max(loY, oy + plot.y1 * k - th - 4);
    tip.style.left = `${Math.max(plotL + 4, Math.min(x, box.width - tw - 4))}px`;
    tip.style.top = `${Math.max(loY, Math.min(oy + pointerY * k - th / 2, hiY))}px`;
  }

  Deck.registerComponent('fig-global-gini-average', (el, props) => {
    const prefix = 'gga' + Math.random().toString(36).slice(2, 7);
    const url = props.dataUrl || DEFAULT_URL;
    const H = props.height || 540;
    const W = 1400;
    el.innerHTML = `<div class="${prefix}-loading">Loading figure data…</div>`;
    let dead = false;

    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${url}`); return r.json(); })
      .then(data => { if (!dead) init(data); })
      .catch(err => {
        if (!dead) el.innerHTML =
          `<div class="${prefix}-loading">Could not load ${url} — run ` +
          `<code>python data/scripts/36_global_gini_averages.py</code> (${err.message})</div>`;
      });

    function init(data) {
      const meta = data.meta;
      const years = meta.years;
      const sampleKeys = meta.samples.map(s => s.key);
      const weightKeys = meta.weightings.map(w => w.key);
      let sample = sampleKeys.includes(props.sample) ? props.sample : sampleKeys[0];
      let weighting = weightKeys.includes(props.weighting) ? props.weighting : weightKeys[0];

      const order = meta.series.map(s => s.key);
      const sources = (Array.isArray(props.sources) && props.sources.length)
        ? props.sources.filter(s => order.includes(s)) : order;
      const shortOf = k => (meta.series.find(s => s.key === k) || { short: k }).short;
      const title = props.title === undefined ? meta.title : (props.title || '');
      const showControls = props.controls !== false;
      const opts = (list, cur) => list.map(o =>
        `<option value="${o.key}"${o.key === cur ? ' selected' : ''}>${esc(o.label)}</option>`).join('');

      el.innerHTML = `
        <style>${styles(prefix)}</style>
        <div class="${prefix}-wrap">
          ${title ? `<div class="${prefix}-title">${esc(title)}</div>` : ''}
          ${showControls ? `
          <div class="${prefix}-controls">
            <label for="${prefix}-w">Average</label>
            <select id="${prefix}-w" class="${prefix}-select">${opts(meta.weightings, weighting)}</select>
            <label for="${prefix}-s">Countries</label>
            <select id="${prefix}-s" class="${prefix}-select">${opts(meta.samples, sample)}</select>
          </div>` : ''}
          <div class="${prefix}-note"></div>
          <div class="${prefix}-chart">
            <svg class="${prefix}-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"></svg>
            <div class="${prefix}-tip"></div>
          </div>
        </div>`;

      const svg = el.querySelector(`.${prefix}-svg`);
      const tip = el.querySelector(`.${prefix}-tip`);
      const note = el.querySelector(`.${prefix}-note`);
      const selW = el.querySelector(`#${prefix}-w`);
      const selS = el.querySelector(`#${prefix}-s`);

      function draw() {
        const w = meta.weightings.find(x => x.key === weighting);
        const s = meta.samples.find(x => x.key === sample);
        note.textContent = `${w.label}. ${w.note} ${s.note}`;
        const series = data.data[sample][weighting];
        const cov = data.coverage[sample];
        const fmt = v => v.toFixed(3);

        const padL = 78, padR = 290, padT = 22, padB = 64;
        const x0 = padL, x1 = W - padR, y1 = H - padB, y0 = padT;
        const xOf = i => x0 + (years.length === 1 ? 0 : (i / (years.length - 1)) * (x1 - x0));

        // A fixed range across selections keeps levels comparable when switching.
        const all = Object.values(data.data).flatMap(bw => Object.values(bw).flatMap(bs => sources.flatMap(k => bs[k])));
        const lo = Math.floor(Math.min(...all) * 20) / 20, hi = Math.ceil(Math.max(...all) * 20) / 20;
        const yOf = v => y1 - ((v - lo) / (hi - lo)) * (y1 - y0);

        const parts = [];
        niceTicks(lo, hi, 6).forEach(v => {
          const y = yOf(v);
          parts.push(`<line class="${prefix}-grid" x1="${x0}" x2="${x1}" y1="${y}" y2="${y}"/>`);
          parts.push(`<text class="${prefix}-tick" x="${x0 - 10}" y="${y + 4}" text-anchor="end">${v.toFixed(2)}</text>`);
        });
        yearTicks(years).forEach(y => {
          const i = years.indexOf(y);
          if (i >= 0) parts.push(`<text class="${prefix}-tick" x="${xOf(i)}" y="${y1 + 20}" text-anchor="middle">${y}</text>`);
        });
        parts.push(`<line class="${prefix}-grid" x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}"/>`);
        parts.push(`<text class="${prefix}-axis" transform="translate(${x0 - 58},${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">Average Gini (${esc(w.label.toLowerCase())})</text>`);

        const ends = [];
        sources.forEach(k => {
          const v = series[k];
          const pts = v.map((x, i) => `${xOf(i).toFixed(1)},${yOf(x).toFixed(1)}`).join(' ');
          const c = COLOR[k] || '#555';
          const dash = DASHED.has(k) ? ' stroke-dasharray="7 5"' : '';
          parts.push(`<polyline points="${pts}" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"${dash}/>`);
          ends.push({ y: yOf(v[v.length - 1]), label: shortOf(k), c, v: v[v.length - 1] });
        });
        ends.sort((a, b) => a.y - b.y);
        const MIN_GAP = 17;
        for (let i = 1; i < ends.length; i++) {
          if (ends[i].y - ends[i - 1].y < MIN_GAP) ends[i].y = ends[i - 1].y + MIN_GAP;
        }
        ends.forEach(e => {
          parts.push(`<text class="${prefix}-label" x="${x1 + 10}" y="${e.y + 4}" fill="${e.c}">${esc(e.label)} ${fmt(e.v)}</text>`);
        });

        const n = cov.pip.n, nw = cov.wid.n;
        const range = a => `${Math.min(...a)}-${Math.max(...a)}`;
        const covText = sample === 'own'
          ? `PIP ${range(n)} countries, WID ${range(nw)}`
          : `${range(n)} countries`;
        parts.push(
          `<text class="${prefix}-source" x="${padL}" y="${H - 8}">` +
          `Deck calculation from the ETL's harmonized bins · ${esc(s.label)}: ${covText} · ` +
          `PIP: nearest survey within 5 years · population at the reference year</text>`
        );
        svg.innerHTML = parts.join('');

        const nearest = lx => {
          const t = years.length === 1 ? 0 : Math.round(((lx - x0) / (x1 - x0)) * (years.length - 1));
          return Math.max(0, Math.min(years.length - 1, t));
        };
        svg.onmousemove = ev => {
          const pt = svg.createSVGPoint();
          pt.x = ev.clientX; pt.y = ev.clientY;
          const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
          svg.querySelectorAll(`.${prefix}-hover`).forEach(nd => nd.remove());
          if (loc.x < x0 || loc.x > x1 || loc.y < y0 || loc.y > y1) { tip.style.opacity = 0; return; }
          const i = nearest(loc.x);
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('class', `${prefix}-hover`);
          line.setAttribute('x1', xOf(i)); line.setAttribute('x2', xOf(i));
          line.setAttribute('y1', y0); line.setAttribute('y2', y1);
          svg.appendChild(line);
          const rows = [...sources]
            .sort((a, b) => series[b][i] - series[a][i])
            .map(k => `<span class="sw" style="background:${COLOR[k] || '#555'}"></span>${esc(shortOf(k))} <b>${fmt(series[k][i])}</b>`);
          const pct = v => Math.round(v * 100) + '%';
          const head = sample === 'own'
            ? `PIP ${n[i]} countries (${pct(cov.pip.pop[i])} of people), WID ${nw[i]}`
            : `${n[i]} countries, ${pct(cov.pip.pop[i])} of world population`;
          tip.innerHTML = `<b>${years[i]}</b> · ${head}<br>${rows.join('<br>')}`;
          placeTip(svg, tip, { x0, x1, y0, y1 }, xOf(i), loc.y);
          tip.style.opacity = 1;
        };
        svg.onmouseleave = () => {
          tip.style.opacity = 0;
          svg.querySelectorAll(`.${prefix}-hover`).forEach(nd => nd.remove());
        };
      }

      draw();
      if (selW) selW.addEventListener('change', () => { weighting = selW.value; draw(); });
      if (selS) selS.addEventListener('change', () => { sample = selS.value; draw(); });
    }

    return () => { dead = true; };
  });
})();
