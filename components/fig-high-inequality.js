/* fig-high-inequality.js — how many countries have high inequality, year by year.
 *
 * The World Bank's "number of countries with high inequality" (Figure 2 of its June 2024 blog)
 * on the deck's series, as sketched on the Prague deck's "Is inequality rising in most places?"
 * slides. One stacked column per year, 1990-2024:
 *
 *   level view    red = at least as unequal as the United States in 2022 (same series, same
 *                 measure), navy = below; the light part of each colour = countries whose nearest
 *                 survey is more than five years away (PIP series only).
 *   change view   red = rising, grey = stable, navy = falling between a base year and each year:
 *                 stable = within +-2 Gini points, or +-5% for the top-10%, top-1% and Palma
 *                 measures. Light = either end more than five years from a survey. A pair resting
 *                 on the SAME survey at both ends is stable by construction; the tooltip counts them.
 *
 * DATA IS NOT EMBEDDED. Fetches data/figures/fig_high_inequality.json, written by
 * data/scripts/38_high_inequality_panel.py (171 countries with a national PIP survey; PIP from
 * each country's nearest survey at any distance, WID at the year itself).
 *
 * Registers `high-inequality-count`. Props (all optional):
 *   series     PIP (default) | PIP_consinc | PIP_topadj | WID_posttax_per_capita | WID_pretax_per_capita
 *   compare    an array of two series keys: two panels side by side on one y axis (the strip
 *              then only highlights them)
 *   metric     gini (default) | top10_share | top1_share | palma
 *   view       level (default) | change
 *   baseYear   the change view's start year (default 2000)
 *   mode       count (default) | share — countries, or share of the covered population
 *   region     "World" (default) or one of PIP's seven regions
 *   controls   false hides the selectors (the series strip stays unless strip:false)
 *   strip      false hides the series strip
 *   height     viewBox height (default 520)
 */
(function () {
  const DATA_URL = 'data/figures/fig_high_inequality.json';
  const C = {
    high: '#D62E2E', low: '#1D3D63', stable: '#9AA5B1',
    grid: 'rgb(238,241,245)', tick: 'rgb(87,114,145)', axis: 'rgb(63,96,138)', faint: 'rgb(140,155,175)',
  };
  const LIGHT = 0.42;               // opacity of the "old data" part of each colour

  function styles(p) {
    return `
      .${p}-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; font-family: var(--font-body); }
      .${p}-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
      .${p}-strip { display: flex; gap: 26px; padding: 0 2px 6px; }
      .${p}-tab { font: 700 17px var(--font-body); color: rgb(190,198,208); background: none; border: 0; padding: 0 0 3px; cursor: pointer;
        border-bottom: 3px solid transparent; }
      .${p}-tab.on { color: var(--ink); border-bottom-color: ${C.high}; }
      .${p}-tab:disabled { cursor: default; }
      .${p}-controls { display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; padding: 0 2px 4px; font: 13px var(--font-body); color: ${C.axis}; }
      .${p}-controls label { font-weight: 600; }
      .${p}-controls select { font: 13px var(--font-body); color: var(--ink); padding: 2px 6px; border: 1px solid rgb(200,210,222); border-radius: 5px; background: #fff; }
      .${p}-title { font: 700 15px var(--font-body); color: var(--ink); padding: 2px 2px 0; }
      .${p}-chart { position: relative; flex: 1; min-height: 0; }
      .${p}-svg { width: 100%; height: 100%; display: block; }
      .${p}-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; font: 12px var(--font-body); color: ${C.axis}; padding: 2px 2px 0; }
      .${p}-legend i { display: inline-block; width: 11px; height: 11px; border-radius: 2px; margin-right: 5px; vertical-align: -1px; }
      .${p}-source { font: 11px var(--font-body); color: ${C.faint}; padding: 2px 2px 0; }
      .${p}-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0; background: rgb(0,33,71); color: #fff;
        font: 12.5px var(--font-body); padding: 6px 9px; border-radius: 6px; white-space: nowrap; line-height: 1.4;
        box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
      .${p}-tip .sw { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; }
    `;
  }
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const pct = v => Math.round(v * 100) + '%';

  function niceMax(v) {
    if (v <= 0) return 1;
    const mag = Math.pow(10, Math.floor(Math.log10(v)));
    const f = v / mag;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * mag;
  }

  // Per year: the categories' country counts and population, for one series.
  function classify(D, st, series) {
    const years = D.meta.years, isPip = series.startsWith('PIP');
    const vals = D.values[series][st.metric];
    const thr = D.meta.threshold.values[series][st.metric];
    const band = D.meta.stable[st.metric];
    const oldAfter = D.meta.old_after;
    const bi = years.indexOf(st.baseYear);
    const keep = D.countries.map(c => st.region === 'World' || c.r === st.region);
    return years.map((y, yi) => {
      const r = { year: y, n: {}, pop: {}, total: 0, totalPop: 0, same: 0, show: st.view === 'level' || yi > bi };
      if (!r.show) return r;
      D.countries.forEach((c, ci) => {
        if (!keep[ci]) return;
        const v = vals[ci][yi], p = D.population[ci][yi];
        let cat;
        if (st.view === 'level') {
          cat = v >= thr ? 'high' : 'low';
          if (isPip && D.distance[ci][yi] > oldAfter) cat += '_old';
        } else {
          const b = vals[ci][bi];
          const d = band.type === 'abs' ? v - b : (b ? v / b - 1 : 0);
          cat = d > band.band ? 'rising' : d < -band.band ? 'falling' : 'stable';
          if (isPip && (D.distance[ci][yi] > oldAfter || D.distance[ci][bi] > oldAfter)) cat += '_old';
          if (isPip && D.survey_year[ci][yi] === D.survey_year[ci][bi]) r.same += 1;
        }
        r.n[cat] = (r.n[cat] || 0) + 1;
        r.pop[cat] = (r.pop[cat] || 0) + p;
        r.total += 1; r.totalPop += p;
      });
      return r;
    });
  }

  // Stacking order, bottom to top, with each category's colour and opacity.
  const STACKS = {
    level: [
      { k: 'low_old', c: C.low, o: LIGHT, label: 'Below the US, survey more than 5 years away' },
      { k: 'low', c: C.low, o: 1, label: 'Below the US' },
      { k: 'high', c: C.high, o: 1, label: 'At least as high as the US' },
      { k: 'high_old', c: C.high, o: LIGHT, label: 'At least as high as the US, survey more than 5 years away' },
    ],
    change: [
      { k: 'falling_old', c: C.low, o: LIGHT, label: 'Falling, an end more than 5 years from a survey' },
      { k: 'falling', c: C.low, o: 1, label: 'Falling' },
      { k: 'stable_old', c: C.stable, o: LIGHT, label: 'Stable, an end more than 5 years from a survey' },
      { k: 'stable', c: C.stable, o: 1, label: 'Stable' },
      { k: 'rising', c: C.high, o: 1, label: 'Rising' },
      { k: 'rising_old', c: C.high, o: LIGHT, label: 'Rising, an end more than 5 years from a survey' },
    ],
  };

  Deck.registerComponent('high-inequality-count', (el, props) => {
    const p = 'hi' + Math.random().toString(36).slice(2, 7);
    const H = props.height || 520, W = 1200;
    el.innerHTML = `<div class="${p}-loading">Loading figure data…</div>`;
    let dead = false;
    fetch(DATA_URL)
      .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
      .then(D => { if (!dead) init(D); })
      .catch(err => {
        if (!dead) el.innerHTML = `<div class="${p}-loading">Could not load ${DATA_URL} — run ` +
          `<code>python data/scripts/38_high_inequality_panel.py</code> (${err.message})</div>`;
      });

    function init(D) {
      const meta = D.meta, years = meta.years;
      const keys = meta.series.map(s => s.key), labelOf = k => meta.series.find(s => s.key === k).label;
      const compare = Array.isArray(props.compare) ? props.compare.filter(k => keys.includes(k)).slice(0, 2) : null;
      const st = {
        series: keys.includes(props.series) ? props.series : keys[0],
        metric: meta.measures.some(m => m.key === props.metric) ? props.metric : 'gini',
        view: props.view === 'change' ? 'change' : 'level',
        baseYear: years.includes(+props.baseYear) ? +props.baseYear : 2000,
        mode: props.mode === 'share' ? 'share' : 'count',
        region: ['World', ...meta.regions].includes(props.region) ? props.region : 'World',
      };
      const panels = () => (compare && compare.length === 2 ? compare : [st.series]);
      const opt = (list, cur) => list.map(([v, l]) => `<option value="${v}"${v === cur ? ' selected' : ''}>${esc(l)}</option>`).join('');
      const showControls = props.controls !== false, showStrip = props.strip !== false;

      el.innerHTML = `
        <style>${styles(p)}</style>
        <div class="${p}-wrap">
          ${showStrip ? `<div class="${p}-strip">${keys.map(k => `<button class="${p}-tab" data-k="${k}"${compare ? ' disabled' : ''}>${esc(labelOf(k))}</button>`).join('')}</div>` : ''}
          ${showControls ? `<div class="${p}-controls">
            <label>Measure</label><select data-c="metric">${opt(meta.measures.map(m => [m.key, m.label]), st.metric)}</select>
            <label>View</label><select data-c="view">${opt([['level', 'At least as high as the US in 2022'], ['change', 'Rising / stable / falling']], st.view)}</select>
            <label class="${p}-base">since</label><select class="${p}-base" data-c="baseYear">${opt(years.slice(0, -1).map(y => [y, String(y)]), st.baseYear)}</select>
            <label>Show</label><select data-c="mode">${opt([['count', 'Number of countries'], ['share', 'Share of population']], st.mode)}</select>
            <label>Region</label><select data-c="region">${opt([['World', 'World'], ...meta.regions.map(r => [r, r])], st.region)}</select>
          </div>` : ''}
          <div class="${p}-title"></div>
          <div class="${p}-chart"><svg class="${p}-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet"></svg><div class="${p}-tip"></div></div>
          <div class="${p}-legend"></div>
          <div class="${p}-source"></div>
        </div>`;
      const svg = el.querySelector(`.${p}-svg`), tip = el.querySelector(`.${p}-tip`);
      const title = el.querySelector(`.${p}-title`), legend = el.querySelector(`.${p}-legend`), source = el.querySelector(`.${p}-source`);
      let hits = [];

      function draw() {
        el.querySelectorAll(`.${p}-tab`).forEach(b => b.classList.toggle('on', panels().includes(b.dataset.k)));
        el.querySelectorAll(`.${p}-base`).forEach(n => { n.style.display = st.view === 'change' ? '' : 'none'; });
        const mLabel = { gini: 'Gini', top10_share: 'top 10% share', top1_share: 'top 1% share', palma: 'Palma ratio' }[st.metric];
        const band = meta.stable[st.metric];
        const bandText = band.type === 'abs' ? `±${Math.round(band.band * 100)} Gini points` : `±${Math.round(band.band * 100)}%`;
        title.textContent = st.view === 'level'
          ? `Countries with a ${mLabel} at least as high as the United States in ${meta.threshold.year}${st.region !== 'World' ? ' · ' + st.region : ''}`
          : `Countries where the ${mLabel} rose, held or fell since ${st.baseYear} (stable: ${bandText})${st.region !== 'World' ? ' · ' + st.region : ''}`;

        const ser = panels(), stacks = STACKS[st.view];
        // The change view starts the year after its base year.
        const first = st.view === 'change' ? years.indexOf(st.baseYear) + 1 : 0;
        const shown = years.slice(first);
        const rows = ser.map(s => classify(D, st, s).slice(first));
        const shareMode = st.mode === 'share';
        const maxN = Math.max(1, ...rows.flat().filter(r => r.show).map(r => r.total));
        const yMax = shareMode ? 1 : niceMax(maxN);
        const padL = 56, padR = 16, padT = 18, padB = 40, gap = 60;
        const pw = (W - padL - padR - gap * (ser.length - 1)) / ser.length;
        const y0 = padT, y1 = H - padB;
        const yOf = v => y1 - (v / yMax) * (y1 - y0);
        const parts = [];
        hits = [];
        ser.forEach((s, j) => {
          const x0 = padL + j * (pw + gap), x1 = x0 + pw;
          const slot = pw / shown.length, bw = Math.max(2, slot * 0.72);
          const xOf = i => x0 + slot * i + (slot - bw) / 2;
          // grid + left axis
          const steps = shareMode || yMax % 4 === 0 ? 4 : 5;
          for (let t = 0; t <= steps; t++) {
            const v = yMax * t / steps, y = yOf(v);
            parts.push(`<line x1="${x0}" x2="${x1}" y1="${y}" y2="${y}" stroke="${C.grid}"/>`);
            if (j === 0) parts.push(`<text x="${x0 - 8}" y="${y + 4}" text-anchor="end" font-size="12" fill="${C.tick}">${shareMode ? pct(v) : Math.round(v)}</text>`);
          }
          if (ser.length > 1) parts.push(`<text x="${x0}" y="${padT - 4}" font-size="14" font-weight="700" fill="rgb(29,61,99)">${esc(labelOf(s))}</text>`);
          rows[j].forEach((r, i) => {
            if (!r.show) return;
            let acc = 0;
            stacks.forEach(sk => {
              const v = shareMode ? (r.pop[sk.k] || 0) / (r.totalPop || 1) : (r.n[sk.k] || 0);
              if (!v) return;
              const ya = yOf(acc + v), yb = yOf(acc);
              parts.push(`<rect x="${xOf(i)}" y="${ya}" width="${bw}" height="${Math.max(0, yb - ya)}" fill="${sk.c}" fill-opacity="${sk.o}"/>`);
              acc += v;
            });
            if ((shown[i] % 5 === 0 && shown.length - i > 2) || i === shown.length - 1 || i === 0) {
              parts.push(`<text x="${xOf(i) + bw / 2}" y="${y1 + 18}" text-anchor="middle" font-size="12" fill="${C.tick}">${shown[i]}</text>`);
            }
            hits.push({ s, i, r, x: xOf(i), w: bw, x0, x1 });
          });
          parts.push(`<line x1="${x0}" x2="${x1}" y1="${y1}" y2="${y1}" stroke="rgb(200,210,222)"/>`);
        });
        parts.push(`<text transform="translate(16,${(y0 + y1) / 2}) rotate(-90)" text-anchor="middle" font-size="12.5" font-weight="600" fill="${C.axis}">${shareMode ? 'Share of the covered population' : 'Number of countries'}</text>`);
        svg.innerHTML = parts.join('');

        const anyPip = ser.some(s => s.startsWith('PIP'));
        legend.innerHTML = stacks.filter(sk => anyPip || !sk.k.endsWith('_old'))
          .slice().reverse().map(sk => `<span><i style="background:${sk.c};opacity:${sk.o}"></i>${esc(sk.label)}</span>`).join('');
        const thr = ser.map(s => `${labelOf(s)} ${fmtVal(meta.threshold.values[s][st.metric])}`).join(' · ');
        source.textContent = `171 countries with a national PIP survey. PIP: each country's nearest survey (either side, any distance); WID: the year itself. ` +
          `US ${meta.threshold.year} threshold: ${thr}. Deck calculation from the ETL's harmonized bins.`;
      }

      function fmtVal(v) { return st.metric === 'gini' ? v.toFixed(3) : st.metric === 'palma' ? v.toFixed(2) : v.toFixed(1) + '%'; }

      svg.addEventListener('mousemove', ev => {
        const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
        const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
        const h = hits.find(z => loc.x >= z.x - 1 && loc.x <= z.x + z.w + 1);
        if (!h) { tip.style.opacity = 0; return; }
        const stacks = STACKS[st.view].slice().reverse(), r = h.r;
        const lines = stacks.filter(sk => r.n[sk.k]).map(sk =>
          `<span class="sw" style="background:${sk.c};opacity:${sk.o}"></span>${esc(sk.label)}: <b>${r.n[sk.k]}</b> (${pct(r.pop[sk.k] / r.totalPop)} of people)`);
        const same = st.view === 'change' && r.same ? `<br>${r.same} rest on the same survey in ${st.baseYear} and ${r.year} (no measured change)` : '';
        tip.innerHTML = `<b>${esc(labelOf(h.s))}, ${r.year}</b> · ${r.total} countries<br>${lines.join('<br>')}${same}`;
        const box = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal, k = Math.min(box.width / vb.width, box.height / vb.height);
        const ox = (box.width - vb.width * k) / 2, oy = (box.height - vb.height * k) / 2;
        let x = ox + (h.x + h.w + 8) * k;
        if (x + tip.offsetWidth > box.width - 4) x = ox + (h.x - 8) * k - tip.offsetWidth;
        tip.style.left = `${Math.max(4, x)}px`;
        tip.style.top = `${Math.max(4, Math.min(oy + loc.y * k - tip.offsetHeight / 2, box.height - tip.offsetHeight - 4))}px`;
        tip.style.opacity = 1;
      });
      svg.addEventListener('mouseleave', () => { tip.style.opacity = 0; });
      el.querySelectorAll(`.${p}-tab`).forEach(b => b.addEventListener('click', () => { if (!compare) { st.series = b.dataset.k; draw(); } }));
      el.querySelectorAll(`.${p}-controls select`).forEach(s => s.addEventListener('change', () => {
        const k = s.dataset.c; st[k] = k === 'baseYear' ? +s.value : s.value; draw();
      }));
      draw();
    }
    return () => { dead = true; };
  });
})();
