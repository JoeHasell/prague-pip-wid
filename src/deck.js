/* ============================================================
 * deck.js — core engine
 *
 * Responsibilities:
 *  - load content/slides.json and components/manifest.json
 *  - render slides (data -> DOM)
 *  - navigation (keys, buttons, URL hash), stage scaling, notes
 *  - component registry + lazy mounting
 *
 * The optional editor (src/editor.js) drives everything through
 * the public API returned at the bottom of this file.
 * ============================================================ */

window.Deck = (() => {
  'use strict';

  const STAGE_W = 1280;
  const STAGE_H = 720;

  const registry = new Map();     // component name -> mount fn
  let data = null;                // parsed slides.json
  let current = 0;                // active slide index
  let editMode = new URLSearchParams(location.search).has('edit');
  const changeListeners = [];     // editor hooks: fn(eventName)

  const $ = (sel, root = document) => root.querySelector(sel);

  /* ----------------------------------------------------------
   * Component registry
   * A component file calls:
   *   Deck.registerComponent('my-name', (el, props, ctx) => {
   *     ...build DOM inside el...
   *     return () => { ...optional cleanup... };
   *   });
   * -------------------------------------------------------- */
  function registerComponent(name, mountFn) {
    registry.set(name, mountFn);
  }

  /* ----------------------------------------------------------
   * Loading
   * -------------------------------------------------------- */
  async function fetchJSON(url) {
    const res = await fetch(`${url}?t=${Date.now()}`); // cache-bust
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    return res.json();
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error(`Failed to load ${src}`));
      document.body.appendChild(s);
    });
  }

  async function loadComponents() {
    let manifest;
    try {
      manifest = await fetchJSON('components/manifest.json');
    } catch (e) {
      console.warn('No component manifest found — continuing without components.', e);
      return;
    }
    for (const file of manifest.components || []) {
      try {
        await loadScript(`components/${file}`);
      } catch (e) {
        console.error(e);
      }
    }
  }

  /* ----------------------------------------------------------
   * Rendering
   * -------------------------------------------------------- */
  function renderBlock(block) {
    if (block.type === 'html') {
      const el = document.createElement('div');
      el.className = 'block block-html';
      el.dataset.blockId = block.id;
      el.innerHTML = block.html || '<p></p>';
      return el;
    }

    if (block.type === 'component') {
      const el = document.createElement('div');
      el.className = 'block block-component';
      el.dataset.blockId = block.id;
      el.dataset.component = block.component;
      if (block.height) el.style.height = `${block.height}px`;
      el.innerHTML = `<div class="component-pending">&#9679; ${escapeHtml(block.component || 'component')}</div>`;
      return el;
    }

    if (block.type === 'row') {
      const el = document.createElement('div');
      el.className = 'block block-row';
      el.dataset.blockId = block.id;
      for (const child of block.children || []) {
        const cell = document.createElement('div');
        cell.className = 'row-cell';
        if (child.width) cell.style.flex = `0 0 ${child.width}`;
        cell.appendChild(renderBlock(child));
        el.appendChild(cell);
      }
      return el;
    }

    const el = document.createElement('div');
    el.className = 'block block-unknown';
    el.textContent = `Unknown block type: ${block.type}`;
    return el;
  }

  /* ----------------------------------------------------------
   * Annotation overlay (freehand pen, lines/arrows, movable text).
   * Stored per-slide in slide.annotations, positioned in the fixed
   * 1280x720 stage coordinate space, rendered above the blocks in
   * both view and edit modes.
   * -------------------------------------------------------- */
  const SVG_NS = 'http://www.w3.org/2000/svg';

  function penPath(pts) {
    if (!pts || !pts.length) return '';
    if (pts.length < 3) return 'M' + pts.map(p => `${p[0]},${p[1]}`).join(' L');
    let d = `M${pts[0][0]},${pts[0][1]}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const mx = (pts[i][0] + pts[i + 1][0]) / 2, my = (pts[i][1] + pts[i + 1][1]) / 2;
      d += ` Q${pts[i][0]},${pts[i][1]} ${mx},${my}`;
    }
    const last = pts[pts.length - 1];
    return d + ` L${last[0]},${last[1]}`;
  }

  function arrowHead(x1, y1, x2, y2, width, color) {
    const ang = Math.atan2(y2 - y1, x2 - x1);
    const h = 10 + width * 1.7;
    const a1 = ang + Math.PI - 0.42, a2 = ang + Math.PI + 0.42;
    const px1 = (x2 + h * Math.cos(a1)).toFixed(1), py1 = (y2 + h * Math.sin(a1)).toFixed(1);
    const px2 = (x2 + h * Math.cos(a2)).toFixed(1), py2 = (y2 + h * Math.sin(a2)).toFixed(1);
    return `<polygon points="${x2},${y2} ${px1},${py1} ${px2},${py2}" fill="${color}"/>`;
  }

  function annotMarkup(list) {
    return (list || []).map(a => {
      const color = a.color || 'rgb(29, 61, 99)', width = a.width || 3.5;
      if (a.type === 'pen') {
        return `<path class="annot annot-pen" data-aid="${a.id}" d="${penPath(a.pts)}" fill="none" `
          + `stroke="${color}" stroke-width="${width}" stroke-linecap="round" stroke-linejoin="round"/>`;
      }
      if (a.type === 'line') {
        return `<g class="annot annot-line" data-aid="${a.id}">`
          + `<line x1="${a.x1}" y1="${a.y1}" x2="${a.x2}" y2="${a.y2}" stroke="${color}" stroke-width="${width}" stroke-linecap="round"/>`
          + (a.arrow ? arrowHead(a.x1, a.y1, a.x2, a.y2, width, color) : '') + `</g>`;
      }
      if (a.type === 'text') {
        return `<text class="annot annot-text" data-aid="${a.id}" x="${a.x}" y="${a.y}" `
          + `font-size="${a.size || 28}" font-weight="${a.weight || 700}" fill="${color}" `
          + `dominant-baseline="hanging" style="font-family:var(--font-body);white-space:pre">${escapeHtml(a.text || '')}</text>`;
      }
      return '';
    }).join('');
  }

  function makeAnnotLayer(slide) {
    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'slide-annot');
    svg.setAttribute('viewBox', `0 0 ${STAGE_W} ${STAGE_H}`);
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.innerHTML = annotMarkup(slide.annotations);
    return svg;
  }

  function renderAnnotations() {
    const activeEl = document.querySelector('.slide.active');
    if (!activeEl) return;
    const svg = activeEl.querySelector('.slide-annot');
    if (svg) svg.innerHTML = annotMarkup(data.slides[current].annotations);
  }

  function renderSlide(slide, index) {
    const el = document.createElement('section');
    el.className = `slide layout-${slide.layout || 'default'}`;
    if (slide.class) el.classList.add(...slide.class.split(/\s+/));
    el.dataset.slideId = slide.id;
    el.dataset.index = index;

    const body = document.createElement('div');
    body.className = 'slide-body';
    for (const block of slide.blocks || []) body.appendChild(renderBlock(block));
    el.appendChild(body);
    el.appendChild(makeAnnotLayer(slide));
    return el;
  }

  function renderAll() {
    unmountAll();
    const stage = $('#stage');
    stage.innerHTML = '';
    data.slides.forEach((slide, i) => stage.appendChild(renderSlide(slide, i)));
    document.title = (data.meta && data.meta.title) || 'Deck';
    if (data.meta && data.meta.accent) {
      document.documentElement.style.setProperty('--accent', data.meta.accent);
    }
    goTo(Math.min(current, data.slides.length - 1), { force: true });
    emit('render');
  }

  /* ----------------------------------------------------------
   * Component mounting — lazy, on first activation of a slide
   * -------------------------------------------------------- */
  const cleanups = new Map(); // element -> cleanup fn

  function findBlockData(blockId, blocks = null) {
    blocks = blocks || data.slides.flatMap(s => s.blocks || []);
    for (const b of blocks) {
      if (b.id === blockId) return b;
      if (b.type === 'row') {
        const hit = findBlockData(blockId, b.children || []);
        if (hit) return hit;
      }
    }
    return null;
  }

  function mountComponentsIn(slideEl) {
    slideEl.querySelectorAll('.block-component:not([data-mounted])').forEach(el => {
      const name = el.dataset.component;
      const mountFn = registry.get(name);
      const block = findBlockData(el.dataset.blockId);
      el.dataset.mounted = 'true';
      if (!mountFn) {
        el.innerHTML = `<div class="component-missing">Component &ldquo;${escapeHtml(name)}&rdquo; is not registered.<br>Check components/manifest.json.</div>`;
        return;
      }
      el.innerHTML = '';
      try {
        const cleanup = mountFn(el, (block && block.props) || {}, { accent: cssVar('--accent'), editMode });
        if (typeof cleanup === 'function') cleanups.set(el, cleanup);
      } catch (e) {
        console.error(`Component "${name}" failed to mount:`, e);
        el.innerHTML = `<div class="component-missing">Component &ldquo;${escapeHtml(name)}&rdquo; threw an error — see console.</div>`;
      }
    });
  }

  function unmountAll() {
    cleanups.forEach((fn, el) => { try { fn(); } catch (e) { console.error(e); } });
    cleanups.clear();
  }

  /* ----------------------------------------------------------
   * Navigation
   * -------------------------------------------------------- */
  function goTo(index, opts = {}) {
    const max = data.slides.length - 1;
    index = Math.max(0, Math.min(max, index));
    if (index === current && !opts.force) return;
    current = index;

    document.querySelectorAll('.slide').forEach(el => {
      el.classList.toggle('active', Number(el.dataset.index) === current);
    });
    const activeEl = document.querySelector('.slide.active');
    if (activeEl) mountComponentsIn(activeEl);

    $('#slide-counter').textContent =
      `${String(current + 1).padStart(2, '0')} / ${String(max + 1).padStart(2, '0')}`;
    $('#progress-fill').style.width = max === 0 ? '100%' : `${(current / max) * 100}%`;

    const slide = data.slides[current];
    $('#notes-body').textContent = (slide && slide.notes) || 'No notes for this slide.';

    history.replaceState(null, '', `#${current + 1}${editMode ? '' : ''}`);
    emit('navigate');
  }

  function next() { goTo(current + 1); }
  function prev() { goTo(current - 1); }

  function bindNavigation() {
    $('#nav-next').addEventListener('click', next);
    $('#nav-prev').addEventListener('click', prev);

    document.addEventListener('keydown', (e) => {
      // Never steal keys from text editing or form fields.
      const t = e.target;
      if (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === 'ArrowRight' || e.key === 'PageDown' || (e.key === ' ' && !editMode)) { e.preventDefault(); next(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); prev(); }
      else if (e.key === 'Home') { e.preventDefault(); goTo(0); }
      else if (e.key === 'End') { e.preventDefault(); goTo(data.slides.length - 1); }
      else if (e.key === 'n' || e.key === 'N') { toggleNotes(); }
    });

    window.addEventListener('hashchange', () => {
      const n = parseInt(location.hash.slice(1), 10);
      if (!Number.isNaN(n)) goTo(n - 1);
    });
  }

  function toggleNotes() {
    const panel = $('#notes-panel');
    panel.hidden = !panel.hidden;
  }

  /* ----------------------------------------------------------
   * Stage scaling — slides are designed at 1280x720 and scaled
   * to fit the viewport, so layout is deterministic.
   * -------------------------------------------------------- */
  function fitStage() {
    const viewport = $('#viewport');
    const stage = $('#stage');
    const pad = 0;
    const availW = viewport.clientWidth - pad;
    const availH = viewport.clientHeight - pad;
    const scale = Math.min(availW / STAGE_W, availH / STAGE_H);
    stage.style.transform = `translate(-50%, -50%) scale(${scale})`;
  }

  /* ----------------------------------------------------------
   * Utilities + editor plumbing
   * -------------------------------------------------------- */
  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  function emit(event) { changeListeners.forEach(fn => fn(event)); }
  function onChange(fn) { changeListeners.push(fn); }

  function remountCurrentSlide() {
    // Re-render just the active slide (used by the editor after prop edits).
    const stage = $('#stage');
    const old = stage.children[current];
    if (!old) return;
    old.querySelectorAll('.block-component').forEach(el => {
      const fn = cleanups.get(el);
      if (fn) { try { fn(); } catch (e) { console.error(e); } cleanups.delete(el); }
    });
    const fresh = renderSlide(data.slides[current], current);
    stage.replaceChild(fresh, old);
    fresh.classList.add('active');
    mountComponentsIn(fresh);
    emit('render');
  }

  /* ----------------------------------------------------------
   * Boot
   * -------------------------------------------------------- */
  async function boot() {
    try {
      data = await fetchJSON('content/slides.json');
    } catch (e) {
      $('#stage').innerHTML =
        `<div class="boot-error">Could not load <code>content/slides.json</code>.<br>` +
        `If you opened this file directly (file://), run <code>node dev-server.js</code> ` +
        `and open the printed URL instead.<br><small>${escapeHtml(e.message)}</small></div>`;
      console.error(e);
      return;
    }

    await loadComponents();

    const fromHash = parseInt(location.hash.slice(1), 10);
    if (!Number.isNaN(fromHash)) current = fromHash - 1;

    renderAll();
    bindNavigation();
    fitStage();
    window.addEventListener('resize', fitStage);
  }

  /* Public API (used by editor.js and component files) */
  return {
    boot,
    registerComponent,
    goTo, next, prev,
    fitStage,
    renderAll,
    remountCurrentSlide,
    renderAnnotations,
    penPath,
    onChange,
    escapeHtml,
    SVG_NS,
    get data() { return data; },
    get current() { return current; },
    get registry() { return registry; },
    get editMode() { return editMode; },
    STAGE_W, STAGE_H,
  };
})();
