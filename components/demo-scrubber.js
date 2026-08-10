/* Demo component: a scrubber — a slider that drives a live figure
 * and bar. Shows the pattern for stateful, reactive components.
 *
 * Props:
 *   label      string above the slider
 *   min, max   slider range (numbers)
 *   start      initial value
 *   unit       string appended to the output
 *   multiplier output = value * multiplier (default 1)
 *   outputLabel  what the computed figure means
 */
Deck.registerComponent('demo-scrubber', (el, props, ctx) => {
  const min = props.min ?? 0;
  const max = props.max ?? 100;
  const start = props.start ?? Math.round((min + max) / 2);
  const mult = props.multiplier ?? 1;
  const unit = props.unit ?? '';

  el.innerHTML = `
    <style>
      .dsc { height: 100%; display: flex; flex-direction: column; justify-content: center; gap: 18px; padding: 26px 30px; }
      .dsc .label { font: 500 15px var(--font-body); color: var(--muted); }
      .dsc input[type=range] { width: 100%; accent-color: ${ctx.accent || 'var(--accent)'}; }
      .dsc .readout { font: 500 46px var(--font-display); color: var(--ink); line-height: 1; }
      .dsc .readout small { font: 700 12px var(--font-body); color: var(--muted); display: block; margin-top: 8px; letter-spacing: 0.06em; text-transform: uppercase; }
      .dsc .bar { height: 10px; background: rgb(235, 238, 242); border-radius: 5px; overflow: hidden; }
      .dsc .bar-fill { height: 100%; background: ${ctx.accent || 'var(--accent)'}; border-radius: 5px; transition: width 0.08s linear; }
    </style>
    <div class="dsc">
      <div class="label">${props.label || 'Drag to explore'}: <strong class="val"></strong></div>
      <input type="range" min="${min}" max="${max}" value="${start}" step="${props.step ?? 1}">
      <div class="readout"><span class="out"></span><small>${props.outputLabel || 'computed output'}</small></div>
      <div class="bar"><div class="bar-fill"></div></div>
    </div>`;

  const slider = el.querySelector('input');
  const val = el.querySelector('.val');
  const out = el.querySelector('.out');
  const fill = el.querySelector('.bar-fill');

  function update() {
    const v = Number(slider.value);
    val.textContent = v.toLocaleString();
    out.textContent = (v * mult).toLocaleString(undefined, { maximumFractionDigits: 1 }) + unit;
    fill.style.width = `${((v - min) / (max - min)) * 100}%`;
  }

  slider.addEventListener('input', update);
  update();
});
