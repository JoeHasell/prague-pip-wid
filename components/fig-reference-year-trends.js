/* fig-reference-year-trends.js — the Q1 "varying reference year" figures.
 *
 * Registers TWO components sharing one dataset and one set of scales:
 *
 *   fig-reference-year-composition
 *       For every REFERENCE YEAR on the x axis, compared against the latest year
 *       in the data: how many countries have seen inequality rise, fall or stay
 *       stable since then — and what share of the covered population lives in
 *       each group. Stacked bands, one column per source (PIP | WID), one row
 *       per measure (# countries | share of population).
 *
 *   fig-reference-year-change
 *       The average change since each reference year, unweighted and
 *       population-weighted — two lines per source, one panel per source.
 *
 * Both carry a metric selector spanning the Gini and three Generalized Entropy
 * indices. The GE parameter alpha sets how sensitive the index is to the top
 * versus the bottom of the distribution, which is the point of offering it:
 *
 *     GE(0) = mean log deviation   bottom-sensitive
 *     GE(1) = Theil index         scale-neutral
 *     GE(2)                       top-sensitive
 *
 * Every metric is computed by OWID's ETL from the SAME harmonised 109-bin
 * distributions for both sources, so PIP and WID are compared on identical
 * definitions rather than through each source's own published headline measure.
 *
 * DATA IS NOT EMBEDDED. Both components fetch
 *     data/figures/fig_reference_year_trends.json
 * produced by data/scripts/22_fig_reference_year_trends.py from the ETL cache.
 * Regenerating the JSON updates the figures; nothing here hard-codes numbers.
 *
 * Colours: the rising/falling/stable triple is Okabe-Ito vermillion / blue /
 * grey — colourblind-safe and lightness-separated — and every band is directly
 * labelled, so the reading never depends on colour alone.
 *
 * Props (all optional, both components):
 *   dataUrl   override the JSON path
 *   title     chart title; pass "" to omit it and give the panels the space
 *   metric    starting metric: gini | mean_log_deviation | theil_index |
 *             generalized_entropy_2   (default: gini)
 *   metrics   restrict the selector to these metric keys, in this order;
 *             pass a single-element array to hide the selector entirely
 *   sources   ordered array of series to show as columns, from:
 *             PIP | WID_pretax_per_adult | WID_posttax_per_adult
 *             (default: ["PIP", "WID_pretax_per_adult"])
 *
 * fig-reference-year-composition only:
 *   measures  which rows to draw: ["countries", "population"] (default both),
 *             or one of them alone
 */
(function () {
  const DEFAULT_URL = 'data/figures/fig_reference_year_trends.json';

  // Okabe-Ito: vermillion (rising), blue (falling), neutral grey (stable).
  const BAND = {
    rising: { fill: '#D55E00', label: 'Rising' },
    stable: { fill: '#BFBFBF', label: 'Stable' },
    falling: { fill: '#0072B2', label: 'Falling' },
  };
  // Stacked bottom to top, so the labels read Falling / Rising / Stable downwards.
  const STACK = ['stable', 'rising', 'falling'];

  const LINE = {
    unweighted: { stroke: '#3E5C76', dash: '5 4', label: 'Unweighted' },
    weighted: { stroke: '#0E6E59', dash: null, label: 'Population weighted' },
  };

  const CHROME = {
    grid: 'rgb(238,241,245)',
    tick: 'rgb(87,114,145)',
    axis: 'rgb(63,96,138)',
    faint: 'rgb(140,155,175)',
  };

  /* Shared CSS, emitted once per component instance under its own prefix. */
  function styles(p) {
    return `
      .${p}-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
      .${p}-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
      .${p}-title { font: 700 19px var(--font-body); color: var(--ink); padding: 0 4px 4px 2px; }
      .${p}-controls { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 0 8px 2px 0; }
      .${p}-controls label { font: 600 13px var(--font-body); color: ${CHROME.axis}; }
      .${p}-select { font: 14px var(--font-body); color: var(--ink); padding: 3px 8px;
        border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 300px; }
      .${p}-note { font: italic 12px var(--font-body); color: rgb(120,135,155); padding: 1px 8px 0 2px; text-align: right; }
      .${p}-chart { position: relative; flex: 1; min-height: 0; }
      .${p}-svg { width: 100%; height: 100%; display: block; }
      .${p}-grid { stroke: ${CHROME.grid}; stroke-width: 1; }
      .${p}-tick { font: 12px var(--font-body); fill: ${CHROME.tick}; }
      .${p}-axis { font: 600 13px var(--font-body); fill: ${CHROME.axis}; }
      .${p}-ptitle { font: 700 14px var(--font-body); fill: var(--ink); }
      .${p}-psub { font: 12px var(--font-body); fill: ${CHROME.faint}; }
      .${p}-band { font: 700 12.5px var(--font-body); }
      .${p}-hover { stroke: rgb(120,135,155); stroke-width: 1; stroke-dasharray: 3 3; }
      .${p}-source { font: 11.5px var(--font-body); fill: ${CHROME.faint}; }
      .${p}-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
        background: rgb(0,33,71); color: #fff;
        font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px;
        white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      .${p}-tip b { font-weight: 700; }
    `;
  }

  /* Fetch + shared scaffolding. `build(data, ui)` draws one frame. */
  function boot(el, props, prefix, defaults, build) {
    const url = props.dataUrl || DEFAULT_URL;
    el.innerHTML = `<div class="${prefix}-loading">Loading figure data…</div>`;
    let dead = false;

    fetch(url)
      .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${url}`); return r.json(); })
      .then(data => { if (!dead) init(data); })
      .catch(err => {
        if (!dead) el.innerHTML =
          `<div class="${prefix}-loading">Could not load ${url} — run ` +
          `<code>python data/scripts/22_fig_reference_year_trends.py</code> (${err.message})</div>`;
      });

    function init(data) {
      const allMetrics = data.meta.metrics;
      const keys = (Array.isArray(props.metrics) && props.metrics.length)
        ? props.metrics.filter(k => allMetrics.some(m => m.key === k))
        : allMetrics.map(m => m.key);
      const metrics = keys.map(k => allMetrics.find(m => m.key === k));
      let metric = (props.metric && keys.includes(props.metric)) ? props.metric : keys[0];

      const sources = (Array.isArray(props.sources) && props.sources.length)
        ? props.sources.filter(s => data.data[s]) : defaults.sources.filter(s => data.data[s]);

      const title = props.title === undefined ? defaults.title : (props.title || '');
      const showSel = metrics.length > 1;

      el.innerHTML = `
        <style>${styles(prefix)}</style>
        <div class="${prefix}-wrap">
          ${title ? `<div class="${prefix}-title">${title}</div>` : ''}
          ${showSel ? `
          <div class="${prefix}-controls">
            <label for="${prefix}-sel">Inequality measure</label>
            <select id="${prefix}-sel" class="${prefix}-select">
              ${metrics.map(m => `<option value="${m.key}"${m.key === metric ? ' selected' : ''}>${m.label}</option>`).join('')}
            </select>
          </div>
          <div class="${prefix}-note"></div>` : ''}
          <div class="${prefix}-chart">
            <svg class="${prefix}-svg" viewBox="0 0 1400 ${defaults.height}" preserveAspectRatio="xMidYMid meet"></svg>
            <div class="${prefix}-tip"></div>
          </div>
        </div>`;

      const svg = el.querySelector(`.${prefix}-svg`);
      const tip = el.querySelector(`.${prefix}-tip`);
      const chart = el.querySelector(`.${prefix}-chart`);
      const note = el.querySelector(`.${prefix}-note`);
      const sel = el.querySelector(`#${prefix}-sel`);

      const ui = { svg, tip, chart, note, data, sources, metricOf: () => metric, prefix };

      function draw() {
        if (note) {
          const m = allMetrics.find(x => x.key === metric);
          note.textContent = m ? m.note : '';
        }
        build(data, ui);
      }
      draw();

      if (sel) {
        sel.addEventListener('change', () => { metric = sel.value; draw(); });
      }
    }

    return () => { dead = true; };
  }

  /* ---------- small shared helpers ---------- */
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const pct = v => (v * 100).toFixed(0) + '%';

  function yearTicks(years) {
    // Decade marks, plus the first and last reference year.
    const out = years.filter(y => y % 10 === 0);
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

  function sourceLabel(meta, key) {
    const s = (meta.series || []).find(x => x.key === key);
    return s ? s : { key, label: key, sub: '' };
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

  function attachHover(ui, panels) {
    // One shared hover: find the nearest reference year in whichever panel the
    // pointer is over, and show every number for that year.
    const { svg, tip, chart } = ui;
    function onMove(ev) {
      const pt = svg.createSVGPoint();
      pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const panel = panels.find(p => loc.x >= p.x0 && loc.x <= p.x1 && loc.y >= p.y0 && loc.y <= p.y1);
      svg.querySelectorAll(`.${ui.prefix}-hover`).forEach(n => n.remove());
      if (!panel) { tip.style.opacity = 0; return; }
      const i = panel.nearest(loc.x);
      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('class', `${ui.prefix}-hover`);
      line.setAttribute('x1', panel.xOf(i)); line.setAttribute('x2', panel.xOf(i));
      line.setAttribute('y1', panel.y0); line.setAttribute('y2', panel.y1);
      svg.appendChild(line);
      tip.innerHTML = panel.tipHtml(i);
      placeTip(svg, tip, panel, panel.xOf(i), loc.y);
      tip.style.opacity = 1;
    }
    svg.addEventListener('mousemove', onMove);
    svg.addEventListener('mouseleave', () => {
      tip.style.opacity = 0;
      svg.querySelectorAll(`.${ui.prefix}-hover`).forEach(n => n.remove());
    });
  }

  /* =====================================================================
   * 1. COMPOSITION — rising / falling / stable, by reference year
   * ===================================================================== */
  Deck.registerComponent('fig-reference-year-composition', (el, props) => {
    const MEASURES = {
      countries: { title: 'Number of countries', fmt: v => String(v), keys: ['rising', 'stable', 'falling'] },
      population: { title: 'Share of population', fmt: pct, keys: ['pop_rising', 'pop_stable', 'pop_falling'] },
    };

    return boot(el, props, 'frc2', {
      title: 'Where has inequality risen — and since when?',
      sources: ['PIP', 'WID_pretax_per_adult'],
      height: 560,
    }, (data, ui) => {
      const { svg, data: d } = ui;
      const meta = d.meta;
      const metric = ui.metricOf();
      const rows = (Array.isArray(props.measures) && props.measures.length
        ? props.measures : ['countries', 'population']).filter(m => MEASURES[m]);
      const cols = ui.sources;

      const W = 1400, H = 560;
      const padL = 74, padR = 150, padT = 34, padB = 74;
      const gapX = 58, gapY = 58;
      const panelW = (W - padL - padR - gapX * (cols.length - 1)) / cols.length;
      const panelH = (H - padT - padB - gapY * (rows.length - 1)) / rows.length;

      const parts = [];
      const panels = [];

      rows.forEach((mkey, ri) => {
        const M = MEASURES[mkey];
        cols.forEach((skey, ci) => {
          const series = d.data[skey] && d.data[skey][metric];
          const x0 = padL + ci * (panelW + gapX);
          const y0 = padT + ri * (panelH + gapY);
          const x1 = x0 + panelW, y1 = y0 + panelH;

          if (!series) {
            parts.push(`<text class="${ui.prefix}-psub" x="${x0 + panelW / 2}" y="${y0 + panelH / 2}" text-anchor="middle">no data for this measure</text>`);
            return;
          }

          const years = series.year;
          const total = mkey === 'countries' ? meta.n_countries : 1;
          const xOf = i => x0 + (years.length === 1 ? panelW / 2 : (i / (years.length - 1)) * panelW);
          const yOf = v => y1 - (v / total) * panelH;

          // Column heading (source) on the top row only.
          if (ri === 0) {
            const s = sourceLabel(meta, skey);
            parts.push(
              `<text class="${ui.prefix}-ptitle" x="${x0}" y="${y0 - 18}">${esc(s.label)}</text>` +
              `<text class="${ui.prefix}-psub" x="${x0}" y="${y0 - 5}">${esc(s.sub || '')}</text>`
            );
          }
          // Row heading (measure) on the first column only.
          if (ci === 0) {
            parts.push(`<text class="${ui.prefix}-axis" transform="translate(${x0 - 52},${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">${M.title}</text>`);
          }

          // Gridlines + y ticks.
          const ticks = mkey === 'countries'
            ? niceTicks(0, total, 4)
            : [0, 0.25, 0.5, 0.75, 1];
          ticks.forEach(t => {
            parts.push(
              `<line class="${ui.prefix}-grid" x1="${x0}" x2="${x1}" y1="${yOf(t)}" y2="${yOf(t)}"/>` +
              `<text class="${ui.prefix}-tick" x="${x0 - 8}" y="${yOf(t) + 4}" text-anchor="end">${M.fmt(t)}</text>`
            );
          });

          // Stacked bands, bottom to top.
          let base = years.map(() => 0);
          const tops = {};
          STACK.forEach((band, bi) => {
            const key = M.keys[['rising', 'stable', 'falling'].indexOf(band)];
            const vals = series[key];
            const upper = vals.map((v, i) => base[i] + v);
            const fwd = upper.map((v, i) => `${xOf(i)},${yOf(v)}`).join(' ');
            const back = base.map((v, i) => `${xOf(base.length - 1 - i)},${yOf(base[base.length - 1 - i])}`).join(' ');
            parts.push(`<polygon points="${fwd} ${back}" fill="${BAND[band].fill}" fill-opacity="0.9"/>`);
            tops[band] = { mid: upper.map((v, i) => (v + base[i]) / 2) };
            base = upper;
            void bi;
          });

          // Direct band labels at the right edge of the last column.
          if (ci === cols.length - 1) {
            // Top to bottom, with a minimum vertical gap: at the far right almost
            // every country is "stable", so the rising and falling bands are thin
            // and their mid-points would otherwise coincide.
            const order = STACK.slice().reverse();
            const MIN_GAP = 17;
            const ys = order.map(band => yOf(tops[band].mid[tops[band].mid.length - 1]));
            for (let i = 1; i < ys.length; i++) {
              if (ys[i] - ys[i - 1] < MIN_GAP) ys[i] = ys[i - 1] + MIN_GAP;
            }
            const overflow = ys[ys.length - 1] - y1;
            if (overflow > 0) for (let i = 0; i < ys.length; i++) ys[i] -= overflow;
            order.forEach((band, i) => {
              parts.push(`<text class="${ui.prefix}-band" x="${x1 + 10}" y="${ys[i] + 4}" fill="${BAND[band].fill}">${BAND[band].label}</text>`);
            });
          }

          // x axis.
          parts.push(`<line class="${ui.prefix}-grid" x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}"/>`);
          yearTicks(years).forEach(y => {
            const i = years.indexOf(y);
            if (i < 0) return;
            parts.push(`<text class="${ui.prefix}-tick" x="${xOf(i)}" y="${y1 + 18}" text-anchor="middle">${y}</text>`);
          });
          if (ri === rows.length - 1) {
            parts.push(`<text class="${ui.prefix}-axis" x="${(x0 + x1) / 2}" y="${y1 + 38}" text-anchor="middle">Compared with ${meta.latest_year}, starting from…</text>`);
          }

          panels.push({
            x0, x1, y0, y1, xOf,
            nearest: lx => {
              const t = years.length === 1 ? 0 : Math.round(((lx - x0) / panelW) * (years.length - 1));
              return Math.max(0, Math.min(years.length - 1, t));
            },
            tipHtml: i => {
              const s = sourceLabel(meta, skey);
              const rows2 = ['rising', 'stable', 'falling'].map(band => {
                const key = M.keys[['rising', 'stable', 'falling'].indexOf(band)];
                return `${BAND[band].label} ${M.fmt(series[key][i])}`;
              }).join(' · ');
              return `<b>${esc(s.label)}, since ${years[i]}</b><br>${rows2}`;
            },
          });
        });
      });

      parts.push(
        `<text class="${ui.prefix}-source" x="${padL}" y="${H - 6}">` +
        `Our World in Data ETL · PIP and WID, ${meta.n_countries} countries in both sources · ` +
        `"stable" = within ±${pct(meta.stable_threshold)} relative change</text>`
      );

      svg.innerHTML = parts.join('');
      attachHover(ui, panels);
    });
  });

  /* =====================================================================
   * 2. CHANGE — average change since each reference year
   * ===================================================================== */
  Deck.registerComponent('fig-reference-year-change', (el, props) => {
    return boot(el, props, 'frch', {
      title: 'Average change in inequality since each reference year',
      sources: ['PIP', 'WID_pretax_per_adult'],
      height: 460,
    }, (data, ui) => {
      const { svg, data: d } = ui;
      const meta = d.meta;
      const metric = ui.metricOf();
      const cols = ui.sources;

      const W = 1400, H = 460;
      const padL = 78, padR = 176, padT = 40, padB = 78;
      const gapX = 64;
      const panelW = (W - padL - padR - gapX * (cols.length - 1)) / cols.length;
      const panelH = H - padT - padB;

      // A shared y domain across panels, so the two sources are comparable.
      let lo = 0, hi = 0;
      cols.forEach(skey => {
        const s = d.data[skey] && d.data[skey][metric];
        if (!s) return;
        s.avg_change.concat(s.avg_change_pw).forEach(v => { lo = Math.min(lo, v); hi = Math.max(hi, v); });
      });
      if (hi === lo) { hi = lo + 1; }
      const padY = (hi - lo) * 0.12;
      lo -= padY; hi += padY;

      const parts = [];
      const panels = [];

      cols.forEach((skey, ci) => {
        const series = d.data[skey] && d.data[skey][metric];
        const x0 = padL + ci * (panelW + gapX);
        const y0 = padT, x1 = x0 + panelW, y1 = y0 + panelH;
        if (!series) {
          parts.push(`<text class="${ui.prefix}-psub" x="${x0 + panelW / 2}" y="${(y0 + y1) / 2}" text-anchor="middle">no data for this measure</text>`);
          return;
        }
        const years = series.year;
        const xOf = i => x0 + (years.length === 1 ? panelW / 2 : (i / (years.length - 1)) * panelW);
        const yOf = v => y1 - ((v - lo) / (hi - lo)) * panelH;

        const s = sourceLabel(meta, skey);
        parts.push(
          `<text class="${ui.prefix}-ptitle" x="${x0}" y="${y0 - 14}">${esc(s.label)}</text>` +
          `<text class="${ui.prefix}-psub" x="${x0}" y="${y0 - 1}">${esc(s.sub || '')}</text>`
        );

        niceTicks(lo, hi, 5).forEach(t => {
          parts.push(`<line class="${ui.prefix}-grid" x1="${x0}" x2="${x1}" y1="${yOf(t)}" y2="${yOf(t)}"/>`);
          if (ci === 0) {
            parts.push(`<text class="${ui.prefix}-tick" x="${x0 - 8}" y="${yOf(t) + 4}" text-anchor="end">${t > 0 ? '+' : ''}${t}</text>`);
          }
        });
        // Zero line — the "no change" reference.
        parts.push(`<line x1="${x0}" x2="${x1}" y1="${yOf(0)}" y2="${yOf(0)}" stroke="rgb(150,163,180)" stroke-width="1.5"/>`);

        const endLabels = [];
        [['unweighted', 'avg_change'], ['weighted', 'avg_change_pw']].forEach(([kind, key]) => {
          const pts = series[key].map((v, i) => `${xOf(i)},${yOf(v)}`).join(' ');
          const L = LINE[kind];
          parts.push(
            `<polyline points="${pts}" fill="none" stroke="${L.stroke}" stroke-width="2.4"` +
            `${L.dash ? ` stroke-dasharray="${L.dash}"` : ''} stroke-linejoin="round"/>`
          );
          if (ci === cols.length - 1) {
            endLabels.push({ y: yOf(series[key][series[key].length - 1]), L });
          }
        });
        // Both lines converge on ~0 at the right edge, so separate the labels.
        endLabels.sort((a, b) => a.y - b.y);
        const MIN_GAP = 17;
        for (let i = 1; i < endLabels.length; i++) {
          if (endLabels[i].y - endLabels[i - 1].y < MIN_GAP) endLabels[i].y = endLabels[i - 1].y + MIN_GAP;
        }
        endLabels.forEach(({ y, L }) => {
          parts.push(`<text class="${ui.prefix}-band" x="${x1 + 10}" y="${y + 4}" fill="${L.stroke}">${L.label}</text>`);
        });

        parts.push(`<line class="${ui.prefix}-grid" x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}"/>`);
        yearTicks(years).forEach(y => {
          const i = years.indexOf(y);
          if (i < 0) return;
          parts.push(`<text class="${ui.prefix}-tick" x="${xOf(i)}" y="${y1 + 18}" text-anchor="middle">${y}</text>`);
        });
        parts.push(`<text class="${ui.prefix}-axis" x="${(x0 + x1) / 2}" y="${y1 + 38}" text-anchor="middle">Compared with ${meta.latest_year}, starting from…</text>`);

        if (ci === 0) {
          parts.push(`<text class="${ui.prefix}-axis" transform="translate(${x0 - 56},${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle">Change in the measure</text>`);
        }

        panels.push({
          x0, x1, y0, y1, xOf,
          nearest: lx => {
            const t = years.length === 1 ? 0 : Math.round(((lx - x0) / panelW) * (years.length - 1));
            return Math.max(0, Math.min(years.length - 1, t));
          },
          tipHtml: i => {
            const f = v => (v > 0 ? '+' : '') + v.toFixed(3);
            return `<b>${esc(s.label)}, since ${years[i]}</b><br>` +
              `Unweighted ${f(series.avg_change[i])} · Population weighted ${f(series.avg_change_pw[i])}`;
          },
        });
      });

      parts.push(
        `<text class="${ui.prefix}-source" x="${padL}" y="${H - 6}">` +
        `Our World in Data ETL · PIP and WID, ${meta.n_countries} countries in both sources · ` +
        `positive = inequality higher in ${meta.latest_year} than in the reference year</text>`
      );

      svg.innerHTML = parts.join('');
      attachHover(ui, panels);
    });
  });
})();
