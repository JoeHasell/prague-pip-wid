/* fig-between-share-trend.js — the between/within split, read across time.
 *
 * One line per series: the between-country share of global MLD (or, via the
 * selector, total / between / within MLD) for every year the two sources share,
 * on the same common sample. Lines are directly labelled at their right end and
 * a shared hover reads every series for the year under the pointer. The years
 * the JSON marks as mostly extrapolated / nowcast are shaded.
 *
 * DATA IS NOT EMBEDDED. Fetches
 *     data/figures/fig_between_share_trend.json
 * produced by data/scripts/27_fig_between_share_trend.py from the ETL cache.
 *
 * Props (all optional):
 *   dataUrl   override the JSON path
 *   title     chart title; pass "" to omit it
 *   metric    starting metric: between_share | mld_total | mld_between | mld_within
 *   metrics   restrict the selector to these keys, in this order; a single-element
 *             array hides the selector
 *   sources   ordered array of series keys to draw (default: all, in bridging order)
 *   height    viewBox height (default 620)
 */
(function () {
  const DEFAULT_URL = 'data/figures/fig_between_share_trend.json';

  // WID side cool, PIP side warm; Okabe-Ito where it fits. Every line is labelled
  // directly, so the reading never depends on colour alone.
  const COLOR = {
    WID_pretax_per_adult: '#0072B2',
    WID_pretax_per_capita: '#56B4E9',
    WID_posttax_per_adult: '#009E73',
    WID_posttax_per_capita: '#5FC9A6',
    WID_posttax_rescaled: '#7B5EA7',
    PIP_topadj: '#B4761A',
    PIP_consinc: '#E69F00',
    PIP: '#D55E00',
  };
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

  Deck.registerComponent('fig-between-share-trend', (el, props) => {
    const prefix = 'bst' + Math.random().toString(36).slice(2, 7);
    const url = props.dataUrl || DEFAULT_URL;
    const H = props.height || 620;
    const W = 1400;
    el.innerHTML = `<div class="${prefix}-loading">Loading figure data…</div>`;
    let dead = false;

    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${url}`); return r.json(); })
      .then(data => { if (!dead) init(data); })
      .catch(err => {
        if (!dead) el.innerHTML =
          `<div class="${prefix}-loading">Could not load ${url} — run ` +
          `<code>python data/scripts/27_fig_between_share_trend.py</code> (${err.message})</div>`;
      });

    function init(data) {
      const meta = data.meta;
      const years = meta.years;
      const allMetrics = meta.metrics;
      const keys = (Array.isArray(props.metrics) && props.metrics.length)
        ? props.metrics.filter(k => allMetrics.some(m => m.key === k))
        : allMetrics.map(m => m.key);
      const metrics = keys.map(k => allMetrics.find(m => m.key === k));
      let metric = (props.metric && keys.includes(props.metric)) ? props.metric : keys[0];

      const order = meta.series.map(s => s.key);
      const sources = (Array.isArray(props.sources) && props.sources.length)
        ? props.sources.filter(s => data.data[s]) : order.filter(s => data.data[s]);
      const shortOf = k => (meta.series.find(s => s.key === k) || { short: k }).short;

      const title = props.title === undefined ? meta.title : (props.title || '');
      const showSel = metrics.length > 1;

      el.innerHTML = `
        <style>${styles(prefix)}</style>
        <div class="${prefix}-wrap">
          ${title ? `<div class="${prefix}-title">${esc(title)}</div>` : ''}
          ${showSel ? `
          <div class="${prefix}-controls">
            <label for="${prefix}-sel">Measure</label>
            <select id="${prefix}-sel" class="${prefix}-select">
              ${metrics.map(m => `<option value="${m.key}"${m.key === metric ? ' selected' : ''}>${esc(m.label)}</option>`).join('')}
            </select>
          </div>
          <div class="${prefix}-note"></div>` : ''}
          <div class="${prefix}-chart">
            <svg class="${prefix}-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"></svg>
            <div class="${prefix}-tip"></div>
          </div>
        </div>`;

      const svg = el.querySelector(`.${prefix}-svg`);
      const tip = el.querySelector(`.${prefix}-tip`);
      const note = el.querySelector(`.${prefix}-note`);
      const sel = el.querySelector(`#${prefix}-sel`);

      function draw() {
        const m = allMetrics.find(x => x.key === metric);
        if (note) note.textContent = m ? m.note : '';
        const isShare = metric === 'between_share';
        const fmt = v => isShare ? (v * 100).toFixed(1) + '%' : v.toFixed(3);
        const fmtTick = v => isShare ? Math.round(v * 100) + '%' : v.toFixed(2);

        const padL = 78, padR = 250, padT = 22, padB = 64;
        const x0 = padL, x1 = W - padR, y1 = H - padB, y0 = padT;
        const xOf = i => x0 + (years.length === 1 ? 0 : (i / (years.length - 1)) * (x1 - x0));

        const vals = sources.flatMap(s => data.data[s][metric]);
        let lo = Math.min(...vals), hi = Math.max(...vals);
        if (isShare) { lo = Math.max(0, Math.floor(lo * 10) / 10 - 0.0); hi = Math.min(1, Math.ceil(hi * 10) / 10); }
        else { const pad = (hi - lo) * 0.08; lo = Math.max(0, lo - pad); hi = hi + pad; }
        const yOf = v => y1 - ((v - lo) / (hi - lo)) * (y1 - y0);

        const parts = [];

        // Shaded "mostly extrapolated / nowcast" years.
        const shadeIdx = years.findIndex(y => y >= meta.shade_from);
        if (shadeIdx >= 0) {
          const xs = xOf(Math.max(0, shadeIdx - 0.5));
          parts.push(`<rect class="${prefix}-shade" x="${xs}" y="${y0}" width="${x1 - xs}" height="${y1 - y0}"/>`);
          parts.push(`<text class="${prefix}-shadelabel" x="${x1 - 4}" y="${y0 + 14}" text-anchor="end">mostly extrapolated / nowcast</text>`);
        }

        // Grid and y ticks.
        niceTicks(lo, hi, 6).forEach(v => {
          const y = yOf(v);
          parts.push(`<line class="${prefix}-grid" x1="${x0}" x2="${x1}" y1="${y}" y2="${y}"/>`);
          parts.push(`<text class="${prefix}-tick" x="${x0 - 10}" y="${y + 4}" text-anchor="end">${fmtTick(v)}</text>`);
        });
        yearTicks(years).forEach(y => {
          const i = years.indexOf(y);
          if (i >= 0) parts.push(`<text class="${prefix}-tick" x="${xOf(i)}" y="${y1 + 20}" text-anchor="middle">${y}</text>`);
        });
        parts.push(`<line class="${prefix}-grid" x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}"/>`);
        parts.push(`<text class="${prefix}-axis" transform="translate(${x0 - 58},${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">${esc(m ? m.label : metric)}</text>`);

        // Lines, then non-overlapping end labels.
        const ends = [];
        sources.forEach(s => {
          const series = data.data[s][metric];
          const pts = series.map((v, i) => `${xOf(i).toFixed(1)},${yOf(v).toFixed(1)}`).join(' ');
          const c = COLOR[s] || '#555';
          parts.push(`<polyline points="${pts}" fill="none" stroke="${c}" stroke-width="2.4" stroke-linejoin="round"/>`);
          ends.push({ y: yOf(series[series.length - 1]), label: shortOf(s), c, v: series[series.length - 1] });
        });
        ends.sort((a, b) => a.y - b.y);
        const MIN_GAP = 17;
        for (let i = 1; i < ends.length; i++) {
          if (ends[i].y - ends[i - 1].y < MIN_GAP) ends[i].y = ends[i - 1].y + MIN_GAP;
        }
        ends.forEach(e => {
          parts.push(`<text class="${prefix}-label" x="${x1 + 10}" y="${e.y + 4}" fill="${e.c}">${esc(e.label)} ${fmt(e.v)}</text>`);
        });

        parts.push(
          `<text class="${prefix}-source" x="${padL}" y="${H - 8}">` +
          `Our World in Data ETL · PIP and WID, ${meta.n_countries} countries in both sources, every year · ` +
          `same countries, constant prices and zero-income floor throughout</text>`
        );

        svg.innerHTML = parts.join('');

        // Shared hover: nearest year, every series.
        const nearest = lx => {
          const t = years.length === 1 ? 0 : Math.round(((lx - x0) / (x1 - x0)) * (years.length - 1));
          return Math.max(0, Math.min(years.length - 1, t));
        };
        svg.onmousemove = ev => {
          const pt = svg.createSVGPoint();
          pt.x = ev.clientX; pt.y = ev.clientY;
          const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
          svg.querySelectorAll(`.${prefix}-hover`).forEach(n => n.remove());
          if (loc.x < x0 || loc.x > x1 || loc.y < y0 || loc.y > y1) { tip.style.opacity = 0; return; }
          const i = nearest(loc.x);
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('class', `${prefix}-hover`);
          line.setAttribute('x1', xOf(i)); line.setAttribute('x2', xOf(i));
          line.setAttribute('y1', y0); line.setAttribute('y2', y1);
          svg.appendChild(line);
          const rows = [...sources]
            .sort((a, b) => data.data[b][metric][i] - data.data[a][metric][i])
            .map(s => `<span class="sw" style="background:${COLOR[s] || '#555'}"></span>${esc(shortOf(s))} <b>${fmt(data.data[s][metric][i])}</b>`);
          tip.innerHTML = `<b>${years[i]}</b><br>${rows.join('<br>')}`;
          placeTip(svg, tip, { x0, x1, y0, y1 }, xOf(i), loc.y);
          tip.style.opacity = 1;
        };
        svg.onmouseleave = () => {
          tip.style.opacity = 0;
          svg.querySelectorAll(`.${prefix}-hover`).forEach(n => n.remove());
        };
      }

      draw();
      if (sel) sel.addEventListener('change', () => { metric = sel.value; draw(); });
    }

    return () => { dead = true; };
  });
})();
