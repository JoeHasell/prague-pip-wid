/* fig-top1-treemap.js — who is in the global top 1%?
 *
 * A treemap of the country-quantile bins that make up the global top 1%,
 * for a selectable scenario (dropdown over the seven series of the Q2
 * bridging charts). DESIGN PRINCIPLE (per Joe): every area in the plot IS
 * data — there are no container boxes for countries or regions whose area
 * means nothing. Instead:
 *   - box area   = the bin's population inside the top 1%
 *   - colour     = world region (legend chips OUTSIDE the plot, above it)
 *   - countries  = demarcated by a heavier, darker border than the thin
 *                  white lines between quantile bins; the country name
 *                  OVERLAYS its bins where it fits
 *   - quantiles  = labelled inside their box where space allows, skipped
 *                  where the box is too small or a country label overlaps
 *                  (the tooltip carries the information in both cases)
 *
 * The layout is a standard squarified treemap computed hierarchically
 * (region -> country -> bin) so regions and countries are contiguous — but
 * only the bin rectangles are DRAWN.
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_top1_treemap.json,
 * produced by data/scripts/16_fig_top1_treemap.py (population accumulated
 * to exactly 1% of the global population; marginal bin clipped;
 * basis-matched populations — the per-adult scenario ranks the world's
 * ADULTS).
 *
 * Props (all optional):
 *   dataUrl  override the JSON path
 *   source   initially selected scenario (e.g. 'WID_posttax_per_capita');
 *            defaults to the first scenario in the JSON
 *   title    undefined -> default title; '' -> no title row
 */
Deck.registerComponent('fig-top1-treemap', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_top1_treemap.json';

  el.innerHTML = `<div class="ftm-loading">Loading figure data…</div>`;
  let dead = false, cleanupInner = null;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) cleanupInner = init(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="ftm-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/16_fig_top1_treemap.py</code> (${err.message})</div>`;
    });

  // ---- squarified treemap (Bruls, Huizing & van Wijk) ----------------
  // items: [{v, ...}] any order; rect: {x, y, w, h}. Mutates items adding
  // x/y/w/h. Areas are proportional to v; sum of areas fills the rect.
  function squarify(items, rect) {
    const sorted = items.slice().sort((a, b) => b.v - a.v);
    const total = sorted.reduce((s, d) => s + d.v, 0);
    if (total <= 0) return;
    const scale = rect.w * rect.h / total;
    let x = rect.x, y = rect.y, w = rect.w, h = rect.h;
    let row = [], rowArea = 0;
    const worst = (row, area, side) => {
      const mx = Math.max(...row.map(d => d.v * scale));
      const mn = Math.min(...row.map(d => d.v * scale));
      const s2 = side * side;
      return Math.max(s2 * mx / (area * area), area * area / (s2 * mn));
    };
    const layoutRow = (row, area) => {
      const horiz = w < h;                 // lay the row along the SHORT side
      const side = horiz ? w : h;
      const thick = area / side;
      let off = 0;
      row.forEach(d => {
        const len = d.v * scale / thick;
        if (horiz) { d.x = x + off; d.y = y; d.w = len; d.h = thick; }
        else { d.x = x; d.y = y + off; d.w = thick; d.h = len; }
        off += len;
      });
      if (horiz) { y += thick; h -= thick; } else { x += thick; w -= thick; }
    };
    sorted.forEach(d => {
      const side = Math.min(w, h);
      if (!row.length) { row.push(d); rowArea = d.v * scale; return; }
      const withD = worst(row.concat(d), rowArea + d.v * scale, side);
      const without = worst(row, rowArea, side);
      if (withD <= without) { row.push(d); rowArea += d.v * scale; }
      else { layoutRow(row, rowArea); row = [d]; rowArea = d.v * scale; }
    });
    if (row.length) layoutRow(row, rowArea);
  }

  function init(data) {
    const srcKeys = Object.keys(data.scenarios);
    let current = (props.source && data.scenarios[props.source])
      ? props.source : srcKeys[0];

    const REGION_SHORT = {
      'North America': 'North America',
      'Western Europe': 'Western Europe',
      'East Asia and Pacific': 'East Asia & Pacific',
      'Latin America and Caribbean': 'Latin America & Caribbean',
      'Middle East, North Africa, Afghanistan and Pakistan': 'MENA + Afgh. & Pakistan',
      'Eastern Europe and Central Asia': 'E. Europe & Central Asia',
      'South Asia': 'South Asia',
      'Sub-Saharan Africa': 'Sub-Saharan Africa',
    };
    const COUNTRY_ABBR = {
      'United States': 'USA', 'United Kingdom': 'UK',
      'United Arab Emirates': 'UAE', 'Saudi Arabia': 'Saudi Ar.',
      'South Korea': 'S. Korea', 'Switzerland': 'Switz.',
      'Netherlands': 'Neth.', 'Germany': 'Germany',
      'Hong Kong': 'HK', 'Singapore': 'SGP', 'Australia': 'AUS',
      'South Africa': 'S. Africa',
    };

    el.innerHTML = `
      <style>
        .ftm-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
        .ftm-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .ftm-top { display: flex; align-items: baseline; gap: 14px; padding: 0 2px 2px 2px; flex-wrap: wrap; }
        .ftm-title { font: 700 19px var(--font-body); color: var(--ink); }
        .ftm-sub { font: 13px var(--font-body); color: rgb(87,114,145); }
        .ftm-controls { margin-left: auto; display: flex; align-items: center; gap: 8px; }
        .ftm-controls label { font: 600 13px var(--font-body); color: rgb(63,96,138); }
        .ftm-select { font: 13.5px var(--font-body); color: var(--ink); padding: 3px 8px;
          border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 330px; }
        .ftm-legend { display: flex; flex-wrap: wrap; gap: 4px 16px; padding: 4px 2px 6px 2px; }
        .ftm-chip { display: inline-flex; align-items: center; gap: 6px; font: 600 12px var(--font-body); color: var(--ink); }
        .ftm-chip.ftm-absent { opacity: 0.32; }
        .ftm-chip .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }
        .ftm-chart { position: relative; flex: 1; min-height: 0; }
        .ftm-svg { width: 100%; height: 100%; display: block; }
        .ftm-bin { stroke: rgba(255,255,255,0.55); stroke-width: 0.6; }
        .ftm-bin:hover { filter: brightness(1.12); }
        .ftm-cty { fill: none; stroke: rgba(15,25,40,0.65); stroke-width: 1.4; pointer-events: none; }
        .ftm-reg { fill: none; stroke: #fff; stroke-width: 2.4; pointer-events: none; }
        .ftm-clab { font-family: var(--font-body); font-weight: 700; fill: #fff;
          paint-order: stroke; stroke: rgba(10,18,30,0.55); stroke-width: 2.6px;
          pointer-events: none; }
        .ftm-qlab { font-family: var(--font-body); fill: rgba(255,255,255,0.92);
          pointer-events: none; }
        .ftm-src { font: 11.5px var(--font-body); color: rgb(140,155,175); padding: 4px 2px 0 2px; }
        .ftm-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%, -100%); background: rgb(0,33,71); color: #fff;
          font: 12.5px var(--font-body); padding: 7px 10px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,0.35); transition: opacity 0.1s; }
        .ftm-tip b { font-size: 13px; }
      </style>
      <div class="ftm-wrap">
        <div class="ftm-top">
          ${props.title === '' ? '' : `<span class="ftm-title">${props.title || 'Who is in the global top 1%?'}</span>`}
          <span class="ftm-sub"></span>
          <span class="ftm-controls">
            <label for="ftm-sel">Series</label>
            <select id="ftm-sel" class="ftm-select">
              ${srcKeys.map(k => `<option value="${k}"${k === current ? ' selected' : ''}>${data.scenarios[k].label}</option>`).join('')}
            </select>
          </span>
        </div>
        <div class="ftm-legend"></div>
        <div class="ftm-chart">
          <svg class="ftm-svg" viewBox="0 0 1400 620" preserveAspectRatio="xMidYMid meet"></svg>
          <div class="ftm-tip"></div>
        </div>
        <div class="ftm-src"></div>
      </div>`;

    const svg = el.querySelector('.ftm-svg');
    const tip = el.querySelector('.ftm-tip');
    const wrap = el.querySelector('.ftm-chart');
    const sel = el.querySelector('#ftm-sel');
    const subEl = el.querySelector('.ftm-sub');
    const legEl = el.querySelector('.ftm-legend');
    const srcEl = el.querySelector('.ftm-src');

    const fmtBin = b => {
      const m = /^p([\d.]+)p([\d.]+)$/.exec(b);
      return m ? `P${m[1]}–${m[2]}` : b;
    };
    const fmtPop = n => n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 1) + 'M'
      : n >= 1e3 ? Math.round(n / 1e3) + 'k' : Math.round(n).toString();
    const money = v => '$' + (v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(0));

    function draw(srcKey) {
      const sc = data.scenarios[srcKey];
      const unit = sc.basis === 'adult' ? 'adults' : 'people';

      // ---- hierarchy: region -> country -> bins -----------------------
      const byRegion = new Map();
      sc.bins.forEach(row => {
        const [ci, ri, bin, income, pop, partial] = row;
        if (!byRegion.has(ri)) byRegion.set(ri, new Map());
        const byCountry = byRegion.get(ri);
        if (!byCountry.has(ci)) byCountry.set(ci, []);
        byCountry.get(ci).push({ v: pop, bin, income, partial });
      });

      const rect = { x: 1, y: 1, w: 1398, h: 618 };
      const regionNodes = Array.from(byRegion.entries()).map(([ri, byCountry]) => {
        const countryNodes = Array.from(byCountry.entries()).map(([ci, bins]) => ({
          ci, bins, v: bins.reduce((s, b) => s + b.v, 0),
        }));
        return { ri, countryNodes, v: countryNodes.reduce((s, c) => s + c.v, 0) };
      });
      squarify(regionNodes, rect);
      regionNodes.forEach(r => {
        squarify(r.countryNodes, r);
        r.countryNodes.forEach(c => squarify(c.bins, c));
      });

      // ---- render ------------------------------------------------------
      const hover = [];
      let binsSvg = '', ctySvg = '', regSvg = '', clabSvg = '', qlabSvg = '';
      const clabBoxes = [];   // country-label bboxes, to keep qlabels clear

      regionNodes.forEach(r => {
        const color = data.regions[r.ri].color;
        const regionName = data.regions[r.ri].name;
        regSvg += `<rect x="${r.x.toFixed(1)}" y="${r.y.toFixed(1)}" width="${r.w.toFixed(1)}" height="${r.h.toFixed(1)}" class="ftm-reg"/>`;
        r.countryNodes.forEach(c => {
          const name = data.countries[c.ci];
          ctySvg += `<rect x="${c.x.toFixed(1)}" y="${c.y.toFixed(1)}" width="${c.w.toFixed(1)}" height="${c.h.toFixed(1)}" class="ftm-cty"/>`;

          // Country label: full name at a size that fits, else abbreviation,
          // else nothing (the tooltip identifies the country regardless).
          let lab = null;
          for (const [txt, minFs] of [[name, 11], [COUNTRY_ABBR[name] || null, 9.5]]) {
            if (!txt) continue;
            for (let fs = 16; fs >= minFs; fs -= 0.5) {
              if (txt.length * fs * 0.62 <= c.w - 8 && fs + 6 <= c.h) { lab = { txt, fs }; break; }
            }
            if (lab) break;
          }
          if (lab) {
            const lx = c.x + c.w / 2, ly = c.y + c.h / 2 + lab.fs * 0.35;
            clabSvg += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle" class="ftm-clab" style="font-size:${lab.fs}px">${lab.txt}</text>`;
            const bw = lab.txt.length * lab.fs * 0.62 + 6, bh = lab.fs + 6;
            clabBoxes.push({ x0: lx - bw / 2, x1: lx + bw / 2, y0: ly - bh + 2, y1: ly + 4 });
          }

          c.bins.forEach(b => {
            binsSvg += `<rect x="${b.x.toFixed(1)}" y="${b.y.toFixed(1)}" width="${Math.max(b.w, 0.4).toFixed(1)}" height="${Math.max(b.h, 0.4).toFixed(1)}" ` +
              `fill="${color}" class="ftm-bin" data-h="${hover.length}"${b.partial ? ' stroke-dasharray="3 2"' : ''}/>`;
            hover.push({
              t: `<b>${name}</b> — ${fmtBin(b.bin)}<br>` +
                 `${money(b.income)}/month average<br>` +
                 `${fmtPop(b.v)} ${unit}${b.partial ? ' (marginal bin, partly included)' : ''}<br>` +
                 `<span style="opacity:0.75">${regionName}</span>`,
            });

            // Quantile label — only if it fits AND no country label overlaps
            // (tooltip takes over otherwise, small boxes first by design)
            const ql = fmtBin(b.bin);
            const fs = 9;
            if (b.w > ql.length * fs * 0.6 + 6 && b.h > fs + 5) {
              const qx = b.x + b.w / 2, qy = b.y + b.h / 2 + fs * 0.35;
              const qw = ql.length * fs * 0.6;
              const clash = clabBoxes.some(bb =>
                qx + qw / 2 > bb.x0 && qx - qw / 2 < bb.x1 && qy > bb.y0 && qy - fs < bb.y1);
              if (!clash) qlabSvg += `<text x="${qx.toFixed(1)}" y="${qy.toFixed(1)}" text-anchor="middle" class="ftm-qlab" style="font-size:${fs}px">${ql}</text>`;
            }
          });
        });
      });

      // bins first, then country borders, then region borders, then labels
      svg.innerHTML = binsSvg + ctySvg + regSvg + qlabSvg + clabSvg;
      svg._hover = hover;

      // ---- furniture ---------------------------------------------------
      subEl.textContent = `Top 1% of the world's ${unit} = ` +
        `${fmtPop(sc.global_pop * data.meta.top_share)} ${unit}; ` +
        `entry income ${money(sc.threshold)}/month`;
      const present = new Set(sc.bins.map(row => row[1]));
      legEl.innerHTML = data.regions.map((r, i) =>
        `<span class="ftm-chip${present.has(i) ? '' : ' ftm-absent'}" title="${r.name}">` +
        `<span class="sw" style="background:${r.color}"></span>${REGION_SHORT[r.name] || r.name}</span>`
      ).join('');
      srcEl.textContent = `Box area = population in the global top 1% (${unit}; WID demography). ` +
        `Bins sorted by average income and accumulated to exactly 1%; the marginal bin is clipped (dashed). ` +
        `${data.meta.year}, int-$ per month, ${data.meta.n_countries} countries. Pipeline: ${data.meta.generated_by}`;
    }

    function onOver(e) {
      const b = e.target.closest && e.target.closest('.ftm-bin');
      if (!b) return;
      const h = svg._hover[+b.dataset.h];
      const cr = b.getBoundingClientRect(), wr = wrap.getBoundingClientRect();
      tip.style.left = Math.max(70, Math.min(wr.width - 70, cr.left + cr.width / 2 - wr.left)) + 'px';
      tip.style.top = Math.max(40, cr.top - wr.top - 4) + 'px';
      tip.innerHTML = h.t;
      tip.style.opacity = '1';
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.ftm-bin')) return;
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
