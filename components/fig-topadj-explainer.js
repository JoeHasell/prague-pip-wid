/* fig-topadj-explainer.js — interactive explainer for the PIP-side modelling
 * chain, for a selectable country:
 *
 *   consumption (observed, blue)            — consumption countries only
 *     -> income basis (vermillion, dashed)  — the consumption→income step, at
 *                                             one of WID's three slopes b
 *       -> top-adjusted (purple / green)    — WID post-tax top grafted, or its
 *                                             shares matched, above the anchor
 *
 * Colours deliberately match the consumption→income explainer slide
 * (consumption blue, income vermillion dashed); the top-income methods add
 * purple (graft) and green (share match). Default country: Indonesia
 * (consumption-based, so every line shows).
 *
 * TWO MODES (prop `mode`):
 *   'chain'   (default) two panels — full distribution + a zoom on the top where
 *             the adjustment acts — with both top-income methods drawn.
 *   'consinc' ONE full-width panel, no top adjustment at all: the consumption
 *             curve against the income basis at ALL THREE slopes. The build-up
 *             frame for the step before the top adjustment.
 *
 * DATA IS NOT EMBEDDED: fetches data/figures/fig_topadj_explainer.json, produced
 * by data/scripts/23_fig_explainers_from_etl.py, which crosses both modelling
 * choices — `consinc[beta]` and `variants[beta]` — so the slope can be varied
 * while both top-1% methods are drawn together. Methods: consinc.py, topadj.py.
 *
 * Props (all optional):
 *   source    replace the footnote line with this text
 *   dataUrl   override the JSON path
 *   country   initial country (default from the JSON meta)
 *   mode      'chain' (default) or 'consinc' — see above
 *   showMatch true to also draw the matched-share top-1% method. Hidden by
 *             default since 2026-09-09 — only the appended method is reported.
 *   betas     true to expose the consumption→income slope as a radio control.
 *             Ignored in 'consinc' mode, which always draws all three. Off by
 *             default, so the older explainer slides stay on the deck's baseline
 *             slope with no extra control to explain.
 */
Deck.registerComponent('fig-topadj-explainer', (el, props, ctx) => {
  const DATA_URL = props.dataUrl || 'data/figures/fig_topadj_explainer.json';
  const CONS_C = '#0072B2';    // consumption (observed)
  const INCB_C = '#D55E00';    // income basis at the deck's baseline slope
  const GRAFT_C = '#7A3E9D';   // graft: WID's shape above the anchor
  const SHARE_C = '#009E73';   // share match: WID's shares above the anchor
  // The three slopes as a SEQUENTIAL ramp of the income-basis hue, light to
  // dark, so they read as one series at three settings rather than three
  // different things — and so the middle one is still the vermillion the other
  // explainer slides use. A single-hue lightness ramp is CVD-safe by
  // construction; this is not a categorical palette.
  const BETA_RAMP = ['#EE9440', INCB_C, '#6E2F00'];
  // ...with a dash pattern per slope as a redundant channel, so the three are
  // separable in greyscale and for anyone who finds a lightness ramp of one hue
  // hard going. Fine dots = flattest, long dashes = steepest.
  const BETA_DASH = ['2 3', '6 4', '11 4'];

  el.innerHTML = `<div class="fte-loading">Loading figure data…</div>`;
  let dead = false, cleanupInner = null;

  fetch(DATA_URL)
    .then(r => { if (!r.ok) throw new Error(`${r.status} fetching ${DATA_URL}`); return r.json(); })
    .then(data => { if (!dead) cleanupInner = init(data); })
    .catch(err => {
      if (!dead) el.innerHTML =
        `<div class="fte-loading">Could not load ${DATA_URL} — run ` +
        `<code>python data/scripts/23_fig_explainers_from_etl.py</code> (${err.message})</div>`;
    });

  function init(data) {
    const MODE = props.mode === 'consinc' ? 'consinc' : 'chain';
    const ALL_BETAS = MODE === 'consinc';           // draw every slope at once
    const BETAS = data.meta.betas || [data.meta.base_beta];
    // Both controls are switchable state. The anchor carries the bin index it
    // corresponds to, which changes with it.
    let beta = data.meta.base_beta;
    const TOP1 = data.meta.top1_start || 0.99;   // where the top 1% begins
    const aIdx = 99;                              // first bin of the top 1%
    const countries = Object.keys(data.countries).sort();
    let current = (props.country && data.countries[props.country])
      ? props.country : data.meta.default_country;

    // Radio groups rather than dropdowns: with three options each, the whole
    // choice set is visible at once and switching is one click, which matters
    // when the comparison between the settings IS the slide.
    const uid = 'fte' + Math.random().toString(36).slice(2, 8);
    const radios = (name, opts, sel) =>
      `<div class="fte-radios" role="radiogroup">` + opts.map(o =>
        `<label class="fte-radio${o.value === sel ? ' on' : ''}">` +
        `<input type="radio" name="${uid}-${name}" value="${o.value}"${o.value === sel ? ' checked' : ''}>` +
        `<span>${o.label}</span></label>`).join('') + `</div>`;

    // The anchor control is gone (2026-09-09): the adjustment is the top 1%,
    // full stop. Both methods are drawn at once instead of being switchable —
    // the whole point is the contrast between them.
    const showBeta = MODE === 'chain' && !!props.betas;

    el.innerHTML = `
      <style>
        .fte-wrap { position: relative; width: 100%; height: 100%; display: flex; flex-direction: column; }
        .fte-loading { padding: 32px; font: 15px var(--font-body); color: rgb(120,135,155); }
        .fte-controls { display: flex; align-items: center; justify-content: flex-end;
          gap: 12px; padding: 0 8px 4px 0; flex-wrap: wrap; }
        .fte-controls label.fte-cl { font: 600 13px var(--font-body); color: rgb(63,96,138); }
        .fte-select { font: 14px var(--font-body); color: var(--ink); padding: 3px 8px;
          border: 1px solid rgb(200,210,222); border-radius: 6px; background: #fff; max-width: 260px; }
        .fte-radios { display: inline-flex; border: 1px solid rgb(200,210,222);
          border-radius: 6px; overflow: hidden; background: #fff; }
        .fte-radio { display: inline-flex; align-items: center; cursor: pointer;
          font: 13px var(--font-body); color: rgb(87,114,145);
          padding: 4px 11px; border-left: 1px solid rgb(224,230,238); }
        .fte-radio:first-child { border-left: none; }
        .fte-radio input { position: absolute; opacity: 0; width: 0; height: 0; }
        .fte-radio.on { background: var(--wash); color: var(--ink); font-weight: 700; }
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
          <label class="fte-cl" for="fte-sel">Country</label>
          <select id="fte-sel" class="fte-select">
            ${countries.map(c => `<option${c === current ? ' selected' : ''}>${c}</option>`).join('')}
          </select>
          ${!showBeta ? '' : `<label class="fte-cl">Cons&rarr;income slope</label>` +
            radios('beta', BETAS.map(b => ({ value: b, label: `b = ${b}` })), beta)}
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
      // `consinc` is keyed by slope and present only for consumption countries;
      // for an income country the income basis IS the observed PIP series at
      // every slope, so fall back to it.
      const isCons = !!d.consinc;
      const baseAt = b => (isCons ? d.consinc[b] : d.pip);

      // Series: [values, colour, dash, label, drawFromAnchorOnly]
      const series = [];
      series.push({ vals: d.pip, color: CONS_C, dash: '',
                    label: isCons ? 'Consumption (observed)' : 'Income (observed)' });
      if (ALL_BETAS) {
        // One income-basis line per slope. For an income country all three ARE
        // the observed series, so drawing three identical lines would present
        // the choice as having an effect where it has none — draw none, and let
        // the heading say why.
        if (isCons) BETAS.forEach((b, i) => series.push({
          vals: d.consinc[b], color: BETA_RAMP[i] || INCB_C,
          dash: BETA_DASH[i] || '6 4', label: `b = ${b}`,
        }));
      } else {
        series.push({ vals: baseAt(beta), color: INCB_C, dash: '6 4',
                      label: isCons ? 'Income basis (imputed)' : 'Income (observed)' });
      }

      if (MODE === 'chain') {
        // Both top-1% methods at the selected slope. The JSON stores only what
        // actually changes (see the script's docstring): one value for match,
        // two for append, and the rank compression append implies is applied
        // here rather than shipped.
        const V = (d.variants || {})[beta] || {};
        const base = baseAt(beta);
        const p1 = 100 * TOP1;                     // 99
        if (V.adjusted) {
          // Both methods treat the top 1% as ONE group, so each is drawn as a
          // FLAT SEGMENT spanning the ranks it covers — not as a run of dots on
          // the percentile grid. (Before the deck moved to 100 bins this drew
          // ten identical points across the ETL's 0.1% slots, implying a
          // resolution that was not in the data.)
          //
          // MATCH IS HIDDEN BY DEFAULT (Joe, 2026-09-09): it lands close enough
          // to append that showing both only complicated the story. The data is
          // still in the JSON and the method still in topadj.py — pass
          // showMatch: true to bring the curve back.
          if (props.showMatch)
            series.push({ xs: [p1, 100], vals: [V.match, V.match], color: GRAFT_C,
                          dash: '', label: "Match WID's top-1% share" });
          // append: every retained rank scales by 0.99, PIP's own top 1% lands
          // flat across [98.01, 99], and WID's percentile is appended flat
          // across [99, 100] — the vertical at 99 is the step between them.
          const xs = [], ys = [];
          for (let i = 0; i < aIdx; i++) { xs.push(mids[i] * TOP1); ys.push(base[i]); }
          xs.push(p1 * TOP1, p1, p1, 100);
          ys.push(V.append.top_pip, V.append.top_pip, V.append.top_wid, V.append.top_wid);
          // The tooltip must not name a grid label here: append RE-RANKS
          // everything (rank x 0.99), so a point sits between the grid's bins.
          // Say what it is — a rank, or one of the two top groups.
          const n = xs.length;
          series.push({ vals: ys, xs: xs, color: SHARE_C, dash: '5 3',
                        label: "Append WID's top 1%",
                        ptLabel: i => i >= n - 2 ? "WID's top 1%, appended (P99\u2013100)"
                          : i >= n - 4 ? `PIP's own top 1%, re-ranked (P${(p1 * TOP1).toFixed(1)}\u2013${p1})`
                          : `at rank P${xs[i].toFixed(1)} (re-ranked from ${labels[i]})` });
        }
      }

      // In 'chain' mode the second series duplicates the first for an income
      // country (income basis == observed); drop the duplicate label.
      const drawn = series.filter((s, i) => !(i === 1 && !isCons && !ALL_BETAS));

      const panels = MODE === 'consinc'
        ? [{ x0: 74, x1: 1370, pmin: 0, pmax: 100, title: 'Full distribution', filter: () => true }]
        : [{ x0: 74, x1: 750, pmin: 0, pmax: 100, title: 'Full distribution', filter: () => true },
           { x0: 856, x1: 1370, pmin: 95, pmax: 100,
             title: 'Zoom: the top 5%', filter: i => mids[i] >= 95 }];
      const yTop = 52, yBot = 396;

      const heading = MODE === 'consinc'
        ? (isCons
            ? `${country}: consumption &rarr; income basis, at WID&rsquo;s three slopes`
            : `${country}: PIP already reports income here &mdash; the slope changes nothing`)
        : `${country}: the PIP-side chain — ` +
          `${isCons ? 'consumption → income basis → top-adjusted' : 'observed income → top-adjusted'}`;
      let out = `<text x="16" y="20" class="fte-ptitle">${heading}</text>`;
      const hover = [];

      // Chip legend, top right on the title line
      let lx = 1370 - drawn.reduce((w, s) => w + s.label.length * 6.6 + 38, 0);
      drawn.forEach(s => {
        out += `<line x1="${lx}" x2="${lx + 18}" y1="16" y2="16" stroke="${s.color}" stroke-width="3"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
        out += `<text x="${lx + 23}" y="20" class="fte-lab" fill="${s.color}" style="font-size:12px">${s.label}</text>`;
        lx += s.label.length * 6.6 + 38;
      });

      panels.forEach((p, pi) => {
        const idx = mids.map((m, i) => i).filter(p.filter);
        const vals = idx.flatMap(i => drawn.flatMap(s => s.vals[i]))
                        .filter(v => v !== undefined && v > 0);
        const ticks = logTicks(Math.min(...vals), Math.max(...vals));
        const ylo = Math.log(Math.min(...vals)) - 0.08;
        const yhi = Math.log(Math.max(...vals)) + 0.08;
        const X = v => p.x0 + (v - p.pmin) / (p.pmax - p.pmin) * (p.x1 - p.x0);
        const Y = v => yBot - (Math.log(v) - ylo) / (yhi - ylo) * (yBot - yTop);

        out += `<text x="${p.x0}" y="${yTop - 14}" class="fte-ptitle" style="font-size:13px">${p.title}</text>`;
        out += ticks.map(t =>
          `<line x1="${p.x0}" x2="${p.x1}" y1="${Y(t)}" y2="${Y(t)}" class="fte-grid"/>` +
          `<text x="${p.x0 - 6}" y="${Y(t) + 4}" text-anchor="end" class="fte-tick">${money(t)}</text>`).join('');
        const xt = MODE === 'consinc' ? [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
          : pi === 0 ? [0, 25, 50, 75, 100] : [90, 92, 94, 96, 98, 100];
        out += xt.filter(t => t >= p.pmin).map(t =>
          `<text x="${X(t)}" y="${yBot + 18}" text-anchor="middle" class="fte-tick">P${t}</text>`).join('');
        if (MODE === 'chain') {
          out += `<line x1="${X(100 * TOP1)}" x2="${X(100 * TOP1)}" y1="${yTop}" y2="${yBot}" class="fte-splice"/>`;
          if (pi === 1) out += `<text x="${X(100 * TOP1) - 6}" y="${yTop + 12}" text-anchor="end" class="fte-splicelab">top 1%</text>`;
        }

        const path = pts => 'M' + pts.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L');
        drawn.forEach(s => {
          // A series may carry its OWN x positions (append re-ranks everything),
          // and may be shorter than the grid.
          const xsOf = s.xs || mids;
          const all = s.xs ? s.xs.map((_, i) => i) : idx;
          const sIdx = (s.fromAnchor && !s.xs ? all.filter(i => i >= aIdx) : all)
                         .filter(i => s.vals[i] !== undefined && s.vals[i] > 0
                                      && xsOf[i] >= p.pmin - 1e-9);
          const pts = sIdx.map(i => [X(xsOf[i]), Y(s.vals[i])]);
          out += `<path d="${path(pts)}" fill="none" stroke="${s.color}" stroke-width="2.5"${s.dash ? ` stroke-dasharray="${s.dash}"` : ''}/>`;
          // Dots only on the zoom panel, where they read; the full-distribution
          // panel packs every percentile into its width and would be a smear.
          if (pi === 1) {
            sIdx.forEach(i => {
              out += `<circle class="fte-dot" data-h="${hover.length}" cx="${X(xsOf[i])}" cy="${Y(s.vals[i])}" r="4" fill="${s.color}" stroke="#fff" stroke-width="1"/>`;
              const where = s.ptLabel ? s.ptLabel(i) : labels[i];
              hover.push({ t: `<b>${country}</b> ${where} — ${s.label}<br>${money(s.vals[i])}/month` });
            });
          }
        });
      });

      out += `<text transform="translate(16,${(yTop + yBot) / 2}) rotate(-90)" text-anchor="middle" class="fte-axis">Income per month (int-$, log scale)</text>`;
      const prof = `Income basis: WID&rsquo;s scaled-logit profile, ratio = ${data.meta.profile_a} + b&nbsp;log(p/(1&minus;p)) (consinc.py)`;
      if (props.source) {
        out += `<text x="74" y="444" class="fte-source">${props.source}</text>`;
        svg.innerHTML = out;
        svg._hover = hover;
        return;
      }
      out += `<text x="74" y="444" class="fte-source">${data.meta.year}, per capita. ${prof}` +
        (MODE === 'consinc'
          ? `, at each of WID&rsquo;s three published slopes b. No top adjustment on this chart.`
          : ` at b = ${beta}. Top 1%: matched to WID&rsquo;s share, or WID&rsquo;s top percentile appended (topadj.py)`) +
        `. Data: fig_topadj_explainer.json</text>`;

      svg.innerHTML = out;
      svg._hover = hover;
    }

    function onOver(e) {
      const dot = e.target.closest && e.target.closest('.fte-dot');
      if (!dot) return;
      const h = svg._hover[+dot.dataset.h];
      tip.innerHTML = h.t;
      Deck.placeTooltip(tip, dot, wrap);
      tip.style.opacity = '1';
    }
    function onOut(e) {
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.fte-dot')) return;
      tip.style.opacity = '0';
    }
    function onSel() { draw(sel.value); tip.style.opacity = '0'; }

    // One handler for both radio groups: keep the `on` class in sync (the native
    // input is visually hidden, so the label carries the state) and redraw.
    function onRadio(e) {
      const input = e.target.closest && e.target.closest('input[type=radio]');
      if (!input) return;
      const group = input.closest('.fte-radios');
      group.querySelectorAll('.fte-radio').forEach(l =>
        l.classList.toggle('on', l.contains(input)));
      beta = input.value;
      onSel();
    }

    draw(current);
    sel.addEventListener('change', onSel);
    const ctrls = el.querySelector('.fte-controls');
    ctrls.addEventListener('change', onRadio);
    svg.addEventListener('mouseover', onOver);
    svg.addEventListener('mouseout', onOut);
    return () => {
      sel.removeEventListener('change', onSel);
      ctrls.removeEventListener('change', onRadio);
      svg.removeEventListener('mouseover', onOver);
      svg.removeEventListener('mouseout', onOut);
    };
  }

  return () => { dead = true; if (cleanupInner) cleanupInner(); };
});
