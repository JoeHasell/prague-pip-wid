/* fig-means-scatter.js — survey means (PIP) vs national-accounts means (WID).
 *
 * Two views of one dataset, chosen with the `mode` prop:
 *   mode "levels" (default)  Y = WID national income mean, per capita ($/month)
 *   mode "ratio"             Y = WID / PIP, the factor by which national
 *                            accounts exceed the survey
 *   mode "share"             Y = PIP / WID as a PERCENTAGE — the share of
 *                            national income the survey captures. The exact
 *                            inverse of "ratio"; the k-multiples land on
 *                            100%, 50%, 33%, 20%, 10%, which for many
 *                            audiences is the more intuitive reading.
 * X is always PIP's survey mean ($/month). Both axes are logarithmic, with
 * ticks on a 1-2-5 sequence so intermediate values stay readable.
 *
 * In "levels" the plot area is SQUARE, so y = x is a true 45-degree diagonal
 * and the y = kx multiples are parallel to it. In "ratio" those multiples
 * become horizontal lines, which is the point of the second view: the eye no
 * longer has to judge distance from a diagonal.
 *
 * Two OLS fits are drawn over the range of the data (never extrapolated):
 * unweighted, and weighted by population. EACH VIEW USES ITS OWN FIT,
 * regressed on the variables that view actually plots (see fits[mode] in the
 * JSON) — nothing is transformed from another view's coefficients, so the
 * slope and R2 printed in the panel always describe the line on screen.
 * (The fitted lines for ratio/share coincide with the transformed levels
 * line, which is an algebraic identity; R2 does NOT, and is much lower in
 * those views. That is why the panel must report the view's own numbers.)
 * Fits are drawn ON TOP of the dots so they stay readable through the cloud.
 *
 * Bubble AREA is proportional to population (radius ~ sqrt(pop)), with a
 * floor so microstates stay visible and hoverable. The scale is anchored to
 * the largest population across EVERY year in the file, so bubbles are
 * comparable between the 1990 and 2023 slides. Set bubbles:false for
 * uniform dots.
 *
 * Colours: Okabe-Ito colourblind-safe palette (PROJECT_NOTES section 7).
 * Region identity is also carried by the legend and the tooltip.
 *
 * Data: data/figures/fig_means_scatter.json (17_fig_means_scatter.py), which
 * holds every year keyed under `years`.
 *
 * Props (all optional):
 *   mode    "levels" (default), "ratio" or "share"
 *   year    "2023" (default from the file) or "1990"
 *   ratios  multiples to draw (default [1, 2, 3, 5, 10])
 *   bubbles false to disable population sizing (default true)
 *   fits    which regressions to draw and list: subset of
 *           ["unweighted", "weighted"] (default both). Use ["unweighted"] on
 *           a build-up slide that introduces the unweighted fit before the
 *           population-weighted one, or [] to drop the fits and the panel's
 *           fit block entirely. Scales are unaffected, so the slides stay
 *           registered.
 *   yDomain [lo, hi] fixed y-axis range, snapped out to 1-2-5 bounds. Use it
 *           to keep two slides on one scale when only one of them hides an
 *           outlier. Any point falling outside is treated as hidden and named
 *           in the note, so a fixed range can never silently clip data.
 *   hide    array of country names to omit from the PLOT only — they stay in
 *           the regression (fits come from the JSON, computed on every
 *           country) and in the "typical gap" summary. Used on the 2023 share
 *           slide, where Venezuela at 285% stretches the axis and squashes
 *           the rest. A note naming the omitted country and its value is
 *           generated automatically, so it cannot go stale.
 *   ratioLabels false to draw the y = kx reference lines without their labels
 *   note    false to suppress the hidden-point note (use when the slide's own
 *           `source` line already says which country is missing)
 *   title   chart title; pass "" (empty) to omit it
 *   source, src
 *   summary      array of concept keys from the data's `ratio_stats` whose
 *                numbers are filled in, e.g. ["pre-tax"]. Draws a small
 *                mean / population-weighted-mean table in the right-hand
 *                panel, below the region legend, with a column per concept in
 *                the data; concepts not listed show a dash. Omit for no table.
 *   valueFormat  "money" (default) or "plain" — tick and tooltip formatting.
 *   axes         levels mode only. Default shares one domain across both axes
 *                (true 45deg ratio diagonals); "independent" scales each axis
 *                to its own data and uses finer ticks. xDomain / yDomain
 *                override either axis in both modes.
 *   scale        "log" (default) or "linear". Linear axes are anchored at 0,
 *                so the ratio references become rays out of the origin; the
 *                log-log fit is then drawn as the power curve it is.
 *                Use "plain" for a dimensionless measure on both axes.
 */
Deck.registerComponent('fig-means-scatter', (el, props, ctx) => {
  const SRC = props.src || 'data/figures/fig_means_scatter.json';
  const MODE = ['ratio', 'share'].includes(props.mode) ? props.mode : 'levels';
  const RATIOS = props.ratios || [1, 2, 3, 5, 10];
  const BUBBLES = props.bubbles !== false;
  const HIDE = new Set(Array.isArray(props.hide) ? props.hide : []);
  const FITS = Array.isArray(props.fits)
    ? props.fits.filter(f => f === 'unweighted' || f === 'weighted')
    : ['unweighted', 'weighted'];
  const R_MIN = 2.6, R_MAX = 26;
  const PALETTE = ['#0072B2', '#E69F00', '#009E73', '#CC79A7',
                   '#56B4E9', '#D55E00', '#7A3E9D', '#444444'];

  let disposed = false;
  el.innerHTML = '<div style="font:14px var(--font-body);color:rgb(140,155,175);padding:8px">Loading…</div>';

  fetch(SRC).then(r => {
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }).then(D => { if (!disposed) draw(D); }).catch(e => {
    el.innerHTML = `<div style="font:14px var(--font-body);color:#b3261e;padding:8px">
      Could not load <code>${SRC}</code> — ${e.message}</div>`;
  });

  // Tick sequence covering [lo, hi], plus the enclosing nice bounds. The 1-2-5
  // mantissas suit an axis spanning several decades; a narrow axis needs finer
  // steps or it gets two labels and no sense of scale, hence MANT below.
  function niceTicks(lo, hi, mant) {
    const SEQ = [];
    for (let e = -3; e <= 7; e++) for (const m of (mant || [1, 2, 5])) SEQ.push(m * Math.pow(10, e));
    const a = [...SEQ].reverse().find(v => v <= lo) ?? SEQ[0];
    const b = SEQ.find(v => v >= hi) ?? SEQ[SEQ.length - 1];
    return { lo: a, hi: b, ticks: SEQ.filter(v => v >= a && v <= b) };
  }

  // Linear axis from 0 to a round bound above `hi`, in 1-2-2.5-5 steps.
  function linTicks(lo, hi) {
    const span = hi > 0 ? hi : 1;
    const pow = Math.pow(10, Math.floor(Math.log10(span / 5)));
    const step = [1, 2, 2.5, 5, 10].map(m => m * pow).find(v => span / v <= 8) || pow * 10;
    const b = Math.ceil(hi / step) * step;
    const ticks = [];
    for (let i = 0, v = 0; v <= b + step / 1e6; v = ++i * step) ticks.push(+v.toFixed(10));
    return { lo: 0, hi: b, ticks };
  }

  function draw(D) {
    const year = String(props.year || D.meta.default_year);
    const Y = D.years[year];
    if (!Y) {
      el.innerHTML = `<div style="font:14px var(--font-body);color:#b3261e;padding:8px">
        No data for year ${year}. Available: ${Object.keys(D.years).join(', ')}</div>`;
      return;
    }
    const allYearPts = Y.points.map(([c, ri, x, y, pop]) => ({ c, ri, x, y, pop, k: y / x }));
    const colorOf = i => PALETTE[i % PALETTE.length];
    const isRatio = MODE === 'ratio', isShare = MODE === 'share';
    // In levels mode both axes are the same quantity, so by default they share
    // one domain and the ratio diagonals come out at a true 45 degrees. That
    // costs a lot of frame when the two ranges barely overlap: `axes:
    // "independent"` scales each axis to its own data instead, keeps the
    // diagonals (still exactly the k-multiple locus, just no longer 45 degrees)
    // and switches to the finer tick sequence.
    const INDEP = props.axes === 'independent';
    const MANT = INDEP ? [1, 1.5, 2, 3, 5, 7] : [1, 2, 5];
    // `scale: "linear"` swaps the log axes for linear ones anchored at zero, so
    // the ratio references become rays fanning out of the origin. The log-log
    // FIT is still the fit that was estimated — on linear axes it is a power
    // curve, so it is drawn sampled rather than as a straight segment.
    const LINEAR = props.scale === 'linear';
    const isDerived = isRatio || isShare;          // y is a pure number, not $
    const vy = p => isRatio ? p.k : (isShare ? 100 / p.k : p.y);

    // Domains span EVERY year in the file, not just the one on screen, so the
    // 1990 and 2023 slides line up exactly and can be flicked back and forth
    // (same convention as gini-pip-wid-scatter). yDomain overrides that with a
    // fixed range — needed when one slide hides an outlier and its sibling
    // does not, since otherwise the two would no longer share a scale.
    const shown = Object.values(D.years).flatMap(
      yr => yr.points.filter(([c]) => !HIDE.has(c))
              .map(([c, ri, x, y, pop]) => ({ x, y, pop, k: y / x })));
    const xs = shown.map(p => p.x), ys = shown.map(p => vy(p));
    const shareDomain = !isDerived && !INDEP;     // one domain, 45deg diagonals
    const xAll = shareDomain ? xs.concat(ys) : xs;
    const axisFor = (lo, hi) => LINEAR ? linTicks(lo, hi) : niceTicks(lo, hi, MANT);
    const X = Array.isArray(props.xDomain)
      ? axisFor(props.xDomain[0], props.xDomain[1])
      : axisFor(Math.min(...xAll), Math.max(...xAll));
    const Yax = Array.isArray(props.yDomain)
      ? axisFor(props.yDomain[0], props.yDomain[1])
      : (shareDomain ? X : axisFor(Math.min(...ys), Math.max(...ys)));

    // Anything outside a FIXED domain would otherwise vanish silently, so it
    // is treated as hidden and named in the note alongside any explicit hides.
    const inRange = p => vy(p) >= Yax.lo && vy(p) <= Yax.hi
                      && p.x >= X.lo && p.x <= X.hi;
    const pts = allYearPts.filter(p => !HIDE.has(p.c) && inRange(p));
    const hidden = allYearPts.filter(p => HIDE.has(p.c) || !inRange(p));

    // Bubble area ~ population, floored so microstates stay visible and
    // clickable. Anchored to the max across all years AND all countries (a
    // hidden country must not change the scale) so slides stay comparable.
    const popMax = Math.max(...Object.values(D.years)
      .flatMap(yr => yr.points.map(pt => pt[4])));
    const rOf = pop => BUBBLES
      ? R_MIN + (R_MAX - R_MIN) * Math.sqrt(Math.max(pop, 0) / popMax)
      : 5.5;

    const hasNote = hidden.length > 0;
    const W = 1000, H = 600;
    const M = { top: 48, right: 26, bottom: hasNote ? 92 : 68, left: 82 };
    const plotH = H - M.top - M.bottom;
    const plotW = shareDomain ? plotH : 560;  // square only on a shared domain
    const panelX = M.left + plotW + 34;

    const L = LINEAR ? (v => v) : Math.log10;
    const px = v => M.left + ((L(v) - L(X.lo)) / (L(X.hi) - L(X.lo))) * plotW;
    const py = v => M.top + plotH - ((L(v) - L(Yax.lo)) / (L(Yax.hi) - L(Yax.lo))) * plotH;

    // Values are money by default. `valueFormat: "plain"` switches the ticks and
    // the tooltip to a bare number, for a dimensionless quantity on both axes
    // (the MLD scatter). Absent the prop, output is byte-identical to before.
    const PLAIN = props.valueFormat === 'plain';
    const money = v => PLAIN ? (+v).toFixed(2) : '$' + Math.round(v).toLocaleString('en-US');
    const perUnit = PLAIN ? '' : '/month';
    const fmtPop = v => v >= 1e9 ? (v / 1e9).toFixed(2) + 'bn'
                      : v >= 1e6 ? (v / 1e6).toFixed(1) + 'm'
                      : v >= 1e3 ? (v / 1e3).toFixed(0) + 'k' : String(Math.round(v));
    const tickMoney = v => PLAIN ? String(+(+v).toPrecision(2))
                         : (v >= 1000 ? '$' + (v / 1000) + 'k' : '$' + v);
    const fmtK = k => (k % 1 ? k.toFixed(1) : k.toFixed(0)) + '×';
    const fmtPct = v => (v % 1 ? v.toFixed(1) : v.toFixed(0)) + '%';
    const yTick = t => isShare ? fmtPct(t) : (isRatio ? fmtK(t) : tickMoney(t));

    const grid =
      X.ticks.map(t =>
        `<line x1="${px(t)}" x2="${px(t)}" y1="${M.top}" y2="${M.top + plotH}" class="ms-grid"/>` +
        `<text x="${px(t)}" y="${M.top + plotH + 20}" text-anchor="middle" class="ms-tick">${tickMoney(t)}</text>`
      ).join('') +
      Yax.ticks.map(t =>
        `<line x1="${M.left}" x2="${M.left + plotW}" y1="${py(t)}" y2="${py(t)}" class="ms-grid"/>` +
        `<text x="${M.left - 10}" y="${py(t) + 4}" text-anchor="end" class="ms-tick">${yTick(t)}</text>`
      ).join('');

    // ---- y = k*x reference lines (diagonals in levels, horizontals in ratio)
    // `ratioLabels: false` keeps the lines and drops their labels — in share
    // mode they sit at 100/50/20/10%, which the y axis already ticks, so the
    // labels read as a second set of tick marks rather than as annotation.
    const REF_LAB = props.ratioLabels !== false;
    const refLines = RATIOS.map(k => {
      const cls = k === 1 ? 'ms-diag' : 'ms-ratio';
      if (isDerived) {
        const v = isShare ? 100 / k : k;
        if (v < Yax.lo || v > Yax.hi) return '';
        return `<line x1="${M.left}" x2="${M.left + plotW}" y1="${py(v)}" y2="${py(v)}" class="${cls}"/>` +
          (REF_LAB
            ? `<text x="${M.left + plotW - 4}" y="${py(v) - 6}" text-anchor="end" class="ms-ratiolabel">` +
              `${isShare ? fmtPct(v) : fmtK(k)}</text>`
            : '');
      }
      // y = kx, clipped to the x AND y domains — with independent axes the line
      // would otherwise run outside the plot.
      const x1 = Math.max(X.lo, Yax.lo / k), x2 = Math.min(X.hi, Yax.hi / k);
      if (!(x2 > x1)) return '';
      const anchor = x2 >= X.hi * 0.999 ? 'end' : 'middle';
      return `<line x1="${px(x1)}" y1="${py(x1 * k)}" x2="${px(x2)}" y2="${py(x2 * k)}" class="${cls}"/>` +
        (REF_LAB
          ? `<text x="${px(x2)}" y="${py(x2 * k) - 7}" text-anchor="${anchor}" class="ms-ratiolabel">${fmtK(k)}</text>`
          : '');
    }).join('');

    // ---- fits: same model, re-expressed for the ratio view -----------------
    const thisX = pts.map(p => p.x);
    const xlo = Math.min(...thisX), xhi = Math.max(...thisX);
    // fits[MODE] is already in this view's units — just evaluate it
    const F = Y.fits[MODE] || Y.fits.levels;
    const fitAt = (f, x) => Math.pow(10, f.intercept) * Math.pow(x, f.slope);
    const fitLine = (f, cls) => {
      if (!LINEAR) {
        const a = fitAt(f, xlo), b = fitAt(f, xhi);
        return `<line x1="${px(xlo)}" y1="${py(a)}" x2="${px(xhi)}" y2="${py(b)}" class="${cls}"/>`;
      }
      const N = 48, pts = [];
      for (let i = 0; i <= N; i++) {
        const x = xlo + (xhi - xlo) * (i / N);
        pts.push(`${px(x).toFixed(1)},${py(fitAt(f, x)).toFixed(1)}`);
      }
      return `<polyline points="${pts.join(' ')}" fill="none" class="${cls}"/>`;
    };
    const FIT_STYLE = { unweighted: 'ms-fit-unw', weighted: 'ms-fit-w' };
    const FIT_NAME = { unweighted: 'Unweighted', weighted: 'Population-weighted' };
    const fits = FITS.map(k => fitLine(F[k], FIT_STYLE[k])).join('');

    // largest population drawn first, so small states stay on top and clickable
    const order = pts.map((p, i) => [p, i]).sort((a, b) => b[0].pop - a[0].pop);
    const dots = order.map(([p, i]) => {
      const r = rOf(p.pop);
      return `<circle class="ms-dot" data-i="${i}" data-baser="${r.toFixed(2)}" ` +
        `cx="${px(p.x)}" cy="${py(vy(p))}" r="${r.toFixed(2)}" fill="${colorOf(p.ri)}" ` +
        `fill-opacity="${BUBBLES ? 0.6 : 0.8}" stroke="#fff" stroke-width="1.1"/>`;
    }).join('');

    // ---- right-hand panel --------------------------------------------------
    const rowH = 21;
    const legend = D.regions.map((r, i) =>
      `<circle cx="6" cy="${i * rowH}" r="5.5" fill="${colorOf(i)}" stroke="#fff" stroke-width="1"/>` +
      `<text x="20" y="${i * rowH + 4}" class="ms-legend-t">${r}</text>`).join('');
    const fy = D.regions.length * rowH + 20;
    const fitRow = (y, cls, name, f) =>
      `<line x1="0" x2="26" y1="${y}" y2="${y}" class="${cls}"/>` +
      `<text x="34" y="${y + 4}" class="ms-legend-t">${name}</text>` +
      `<text x="34" y="${y + 21}" class="ms-legend-s">slope ${f.slope.toFixed(2)} · R² ${f.r2.toFixed(2)}</text>`;
    // Optional summary table, in the right-hand panel below the region legend
    // (and below the fit block, when there is one). `summary` lists the concepts
    // whose numbers are FILLED IN; every concept in the data still gets a
    // column, so a build-up slide can leave one blank and its sibling fill it
    // without the table changing shape or position.
    const summarySection = (yOff) => {
      const fill = Array.isArray(props.summary) ? props.summary : null;
      const stats = Y.ratio_stats;
      if (!fill || !stats) return '';
      const cols = Object.keys(stats);
      const ROWS = [['Mean', 'mean'], ['Pop-weighted mean', 'pop_weighted_mean']];
      const labW = 112, colW = 84, rH = 19;
      const cx = i => labW + i * colW + colW / 2;
      const cell = v => v == null ? '—' : v.toFixed(2) + '×';
      return `<g transform="translate(0,${yOff})">` +
        `<text x="0" y="0" class="ms-panel-h">WID ÷ PIP, within-country MLD</text>` +
        cols.map((c, i) =>
          `<text x="${cx(i)}" y="20" text-anchor="middle" class="ms-sum-c">WID ${c}</text>`
        ).join('') +
        `<line x1="0" x2="${labW + cols.length * colW}" y1="27" y2="27" class="ms-sum-rule"/>` +
        ROWS.map(([label, key], r) => {
          const y = 27 + 18 + r * rH;
          return `<text x="0" y="${y}" class="ms-sum-l">${label}</text>` +
            cols.map((c, i) => `<text x="${cx(i)}" y="${y}" text-anchor="middle" ` +
              `class="ms-sum-v${fill.includes(c) ? '' : ' ms-sum-off'}">` +
              `${fill.includes(c) ? cell(stats[c][key]) : '—'}</text>`).join('');
        }).join('') +
        `</g>`;
    };
    // Sits after the legend, or after the fit block when fits are drawn.
    const sumY = fy + (FITS.length ? 22 + FITS.length * 46 + 10 : 0);

    // TOP-ALIGN the panel so the CAP of "Region" meets the top of the plotting
    // box. The header's baseline sits 14 above the panel origin, and its caps
    // rise about 0.72 of the 11.5px face above that baseline, so the origin has
    // to start that much lower. The +1 errs a hair BELOW the box edge rather
    // than above it (Joe's call) — a header poking above the plot reads as
    // misaligned, one sitting just inside does not.
    // 11.4 is the measured ascent of the 11.5px header face above its baseline
    // (getBBox in the browser, not a guess), and the baseline sits 14 above the
    // panel origin. +1 keeps the cap a hair inside the box rather than over it.
    const PANEL_HDR_ASCENT = 11.4;
    const panelY = M.top + 14 + PANEL_HDR_ASCENT + 1;

    const panel =
      `<g transform="translate(${panelX},${panelY})">` +
      `<text x="0" y="-14" class="ms-panel-h">Region</text>` + legend +
      (FITS.length
        // Just "Log-log fit" — the suffix naming what was regressed on what
        // duplicated the axis labels, which say it already.
        ? `<text x="0" y="${fy}" class="ms-panel-h">Log-log fit</text>` +
          FITS.map((k, i) => fitRow(fy + 22 + i * 46, FIT_STYLE[k], FIT_NAME[k], F[k])).join('')
        : '') +
      summarySection(sumY) +
      `</g>`;

    const yLabel = isShare ? (D.meta.share_label || 'PIP survey mean as a share of WID national income')
                 : isRatio ? D.meta.ratio_label : D.meta.y_label;
    // A hidden point may be off the TOP or the BOTTOM of a fixed domain, and the
    // value is only money in levels mode, so both are read off the point rather
    // than assumed. The regression clause applies only when a fit is drawn.
    // props.note === false: the slide has folded the hidden point into its own
    // source line, so the separate note would repeat it.
    const hiddenNote = props.note !== false && hidden.length
      ? hidden.map(p => {
          const v = vy(p), high = v > Yax.hi;
          const shown = isShare ? `share of ${fmtPct(v)}`
                      : isRatio ? `ratio of ${fmtK(v)}`
                      : `value of ${money(p.y)}${perUnit}`;
          return `${p.c}, an outlier with a very ${high ? 'high' : 'low'} ${shown}, is not shown`;
        }).join('; ') +
        (FITS.length ? '. It is still included in the regression.' : '.')
      : '';
    // undefined -> the default narrative title; empty string -> no title at all
    // (the `||` idiom alone could not express "no title", since '' is falsy).
    const title = props.title === undefined ? `${D.meta.title} — ${year}` : (props.title || '');
    const source = props.source ||
      `Data: World Bank PIP and WID.world, processed by Our World in Data. ${Y.n_countries} countries, ${year}. ${D.meta.units}`;

    el.innerHTML = `
      <style>
        .ms-wrap { position: relative; width: 100%; height: 100%; }
        .ms-svg { width: 100%; height: 100%; display: block; }
        .ms-title { font: 700 20px var(--font-body); fill: var(--ink); }
        .ms-grid { stroke: rgb(235,238,242); stroke-width: 1; }
        .ms-tick { font: 12.5px var(--font-body); fill: rgb(87,114,145); }
        .ms-axis { font: 600 14px var(--font-body); fill: rgb(63,96,138); }
        .ms-diag { stroke: rgb(120,138,160); stroke-width: 1.6; }
        .ms-ratio { stroke: rgb(186,197,211); stroke-width: 1; stroke-dasharray: 4 4; }
        .ms-ratiolabel { font: italic 11.5px var(--font-body); fill: rgb(140,155,175); }
        .ms-fit-unw { stroke: rgb(29,61,99); stroke-width: 2.6; }
        .ms-fit-w { stroke: rgb(206,38,30); stroke-width: 2.6; stroke-dasharray: 7 4; }
        .ms-fit-halo { stroke: #fff; stroke-width: 5.5; stroke-opacity: .85; }
        .ms-dot { cursor: pointer; transition: r .08s ease; }
        .ms-panel-h { font: 700 11.5px var(--font-body); fill: rgb(87,114,145);
          letter-spacing: .09em; text-transform: uppercase; }
        .ms-legend-t { font: 12.5px var(--font-body); fill: var(--ink); }
        .ms-legend-s { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
        .ms-source { font: 11.5px var(--font-body); fill: rgb(140,155,175); }
        .ms-sum-h { font: 700 10.5px var(--font-body); fill: rgb(120,135,155);
                    letter-spacing: .06em; text-transform: uppercase; }
        .ms-sum-c { font: 700 11.5px var(--font-body); fill: rgb(63,96,138); }
        .ms-sum-l { font: 12px var(--font-body); fill: var(--ink); }
        .ms-sum-v { font: 700 13px var(--font-body); fill: var(--ink); }
        .ms-sum-off { font-weight: 400; fill: rgb(185,194,208); }
        .ms-sum-rule { stroke: rgb(226,231,238); stroke-width: 1; }
        .ms-note { font: italic 12px var(--font-body); fill: rgb(87,114,145); }
        .ms-tip { position: absolute; pointer-events: none; z-index: 5; opacity: 0;
          transform: translate(-50%,-100%); background: rgb(0,33,71); color: #fff;
          font: 13px var(--font-body); padding: 8px 11px; border-radius: 6px;
          white-space: nowrap; box-shadow: 0 6px 18px rgba(0,12,28,.35); transition: opacity .1s; }
        .ms-tip b { font-weight: 700; }
        .ms-tip .r { color: rgba(255,255,255,.82); margin-top: 3px; }
        .ms-tip .f { margin-top: 5px; font-weight: 700; }
        .ms-tip .sw { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; }
      </style>
      <div class="ms-wrap">
        <svg class="ms-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
          ${title ? `<text x="${M.left}" y="28" class="ms-title">${title}</text>` : ''}
          ${grid}${refLines}${dots}
          <g class="ms-fits">${fits.replace(/class="ms-fit-(unw|w)"/g, 'class="ms-fit-halo"')}${fits}</g>
          ${panel}
          <text transform="translate(20,${M.top + plotH / 2}) rotate(-90)" text-anchor="middle"
                class="ms-axis">${yLabel}</text>
          <text x="${M.left + plotW / 2}" y="${M.top + plotH + 46}" text-anchor="middle"
                class="ms-axis">${D.meta.x_label}</text>
          ${hiddenNote ? `<text x="${M.left}" y="${M.top + plotH + 70}" class="ms-note">${hiddenNote}</text>` : ''}
          <text x="${M.left}" y="${H - 6}" class="ms-source">${source}</text>
        </svg>
        <div class="ms-tip"></div>
      </div>`;

    const wrap = el.querySelector('.ms-wrap'), tip = el.querySelector('.ms-tip');
    const svg = el.querySelector('.ms-svg');
    let active = null;

    function showTip(p, circle) {
      const factor = isShare
        ? `Survey captures ${fmtPct(100 / p.k)} of national income`
        : (p.k >= 1 ? `WID is ${p.k.toFixed(2)}× PIP`
                    : `WID is ${(1 / p.k).toFixed(2)}× LOWER than PIP`);
      tip.innerHTML =
        `<div><span class="sw" style="background:${colorOf(p.ri)}"></span><b>${p.c}</b>` +
        `<span style="opacity:.7"> (${year})</span></div>` +
        `<div class="r">${D.regions[p.ri]}</div>` +
        `<div class="r">${D.meta.x_tip_label || 'PIP survey mean'}: ${money(p.x)}${perUnit}</div>` +
        `<div class="r">${D.meta.y_tip_label || 'WID national income'}: ${money(p.y)}${perUnit}</div>` +
        `<div class="r">Population: ${fmtPop(p.pop)}</div>` +
        `<div class="f">${factor}</div>`;
      Deck.placeTooltip(tip, circle, wrap);
      tip.style.opacity = '1';
    }
    function reset() { if (active) { active.setAttribute('r', active.dataset.baser); active = null; } }
    function onOver(e) {
      const c = e.target.closest && e.target.closest('.ms-dot');
      if (!c || c === active) return;
      reset(); active = c;
      c.setAttribute('r', (parseFloat(c.dataset.baser) + 2.5).toFixed(2));
      showTip(pts[+c.dataset.i], c);
    }
    function onOut(e) {
      const c = e.target.closest && e.target.closest('.ms-dot');
      if (!c) return;
      const to = e.relatedTarget;
      if (to && to.closest && to.closest('.ms-dot')) return;
      reset(); tip.style.opacity = '0';
    }
    function onLeave() { reset(); tip.style.opacity = '0'; }
    svg.addEventListener('mouseover', onOver);
    svg.addEventListener('mouseout', onOut);
    wrap.addEventListener('mouseleave', onLeave);
    el._cleanup = () => {
      svg.removeEventListener('mouseover', onOver);
      svg.removeEventListener('mouseout', onOut);
      wrap.removeEventListener('mouseleave', onLeave);
    };
  }

  return () => { disposed = true; if (el._cleanup) el._cleanup(); };
});
