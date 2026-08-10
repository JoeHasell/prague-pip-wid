/* Demo component: interactive line chart (pure SVG, no libraries).
 *
 * Props:
 *   title   string
 *   unit    string appended to values, e.g. "%"
 *   series  [{ label, values: [{x, y}, ...] }, ...]  (falls back to demo data)
 *
 * This file doubles as the reference pattern for writing components:
 * register a mount function, build DOM inside `el`, optionally return
 * a cleanup function.
 */
Deck.registerComponent('demo-line-chart', (el, props, ctx) => {
  const series = props.series || [
    { label: 'Scenario A', values: Array.from({ length: 13 }, (_, i) => ({ x: 2014 + i, y: 18 + i * 3.2 + Math.sin(i) * 7 })) },
    { label: 'Scenario B', values: Array.from({ length: 13 }, (_, i) => ({ x: 2014 + i, y: 68 + i * 0.8 + Math.cos(i * 0.8) * 5 })) },
  ];
  const unit = props.unit || '';
  const colors = ['#3360A9', '#B13507', '#578145', '#883039']; // OWID-style categorical palette

  const PAD = { top: 44, right: 24, bottom: 34, left: 52 };
  const W = 900, H = 420;

  const xs = series.flatMap(s => s.values.map(v => v.x));
  const ys = series.flatMap(s => s.values.map(v => v.y));
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(0, ...ys), yMax = Math.max(...ys) * 1.08;

  const px = x => PAD.left + ((x - xMin) / (xMax - xMin)) * (W - PAD.left - PAD.right);
  const py = y => H - PAD.bottom - ((y - yMin) / (yMax - yMin)) * (H - PAD.top - PAD.bottom);

  const yTicks = 4;
  let grid = '';
  for (let i = 0; i <= yTicks; i++) {
    const yVal = yMin + (i / yTicks) * (yMax - yMin);
    grid += `<line x1="${PAD.left}" x2="${W - PAD.right}" y1="${py(yVal)}" y2="${py(yVal)}" stroke="rgb(235, 238, 242)" stroke-width="1"/>` +
            `<text x="${PAD.left - 8}" y="${py(yVal) + 4}" text-anchor="end" class="tick">${Math.round(yVal)}${unit}</text>`;
  }
  const xStep = Math.max(1, Math.round((xMax - xMin) / 6));
  for (let x = xMin; x <= xMax; x += xStep) {
    grid += `<text x="${px(x)}" y="${H - PAD.bottom + 20}" text-anchor="middle" class="tick">${x}</text>`;
  }

  const paths = series.map((s, i) => {
    const d = s.values.map((v, j) => `${j ? 'L' : 'M'}${px(v.x)},${py(v.y)}`).join(' ');
    return `<path d="${d}" fill="none" stroke="${colors[i % colors.length]}" stroke-width="2.5"/>` +
           `<text x="${px(s.values.at(-1).x) - 6}" y="${py(s.values.at(-1).y) - 10}" text-anchor="end" ` +
           `fill="${colors[i % colors.length]}" class="series-label">${s.label}</text>`;
  }).join('');

  el.innerHTML = `
    <style>
      .dlc { width: 100%; height: 100%; display: block; }
      .dlc .title { font: 700 17px var(--font-body); fill: var(--ink); }
      .dlc .tick { font: 12px var(--font-body); fill: rgb(87, 114, 145); }
      .dlc .series-label { font: 600 13px var(--font-body); }
      .dlc .tt-box { fill: rgb(0, 33, 71); rx: 3; }
      .dlc .tt-text { font: 12px var(--font-body); fill: #fff; }
    </style>
    <svg class="dlc" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
      <text x="${PAD.left}" y="26" class="title">${props.title || 'Demo line chart'}</text>
      ${grid}${paths}
      <g class="hover" style="display:none">
        <line class="hover-line" y1="${PAD.top}" y2="${H - PAD.bottom}" stroke="rgb(160, 175, 194)" stroke-dasharray="3 3"/>
        <rect class="tt-box" width="150" height="0"></rect>
        <g class="tt-rows"></g>
      </g>
    </svg>`;

  // Hover: nearest x across all series
  const svg = el.querySelector('svg');
  const hover = svg.querySelector('.hover');
  const hoverLine = svg.querySelector('.hover-line');
  const ttBox = svg.querySelector('.tt-box');
  const ttRows = svg.querySelector('.tt-rows');
  const allX = [...new Set(xs)].sort((a, b) => a - b);

  function onMove(e) {
    const rect = svg.getBoundingClientRect();
    const mx = ((e.clientX - rect.left) / rect.width) * W;
    const dataX = allX.reduce((best, x) => Math.abs(px(x) - mx) < Math.abs(px(best) - mx) ? x : best, allX[0]);
    const cx = px(dataX);
    hover.style.display = '';
    hoverLine.setAttribute('x1', cx);
    hoverLine.setAttribute('x2', cx);
    const rows = series
      .map((s, i) => ({ s, i, v: s.values.find(v => v.x === dataX) }))
      .filter(r => r.v);
    const bx = cx + 160 > W ? cx - 158 : cx + 8;
    ttBox.setAttribute('x', bx);
    ttBox.setAttribute('y', PAD.top);
    ttBox.setAttribute('height', 22 + rows.length * 18);
    ttRows.innerHTML =
      `<text class="tt-text" x="${bx + 10}" y="${PAD.top + 17}" font-weight="600">${dataX}</text>` +
      rows.map((r, k) =>
        `<text class="tt-text" x="${bx + 10}" y="${PAD.top + 35 + k * 18}">` +
        `<tspan fill="${colors[r.i % colors.length]}">&#9632;</tspan> ${r.s.label}: ${r.v.y.toFixed(1)}${unit}</text>`
      ).join('');
  }

  function onLeave() { hover.style.display = 'none'; }

  svg.addEventListener('mousemove', onMove);
  svg.addEventListener('mouseleave', onLeave);

  return () => {
    svg.removeEventListener('mousemove', onMove);
    svg.removeEventListener('mouseleave', onLeave);
  };
});
