/* ============================================================
 * editor.js — inline point-and-click editor
 *
 * Loaded only when the URL contains ?edit. Everything here works
 * against the live Deck.data object, then persists via:
 *   1. POST /save  (dev-server.js writes content/slides.json)
 *   2. fallback: download slides.json (works on the static site)
 * A working draft is kept in localStorage so nothing is lost.
 * ============================================================ */

(() => {
  'use strict';

  const DRAFT_KEY = `deckDraft:${location.pathname}`;
  let dirty = false;
  let draftTimer = null;

  const $ = (sel, root = document) => root.querySelector(sel);
  const newId = (prefix) => `${prefix}-${Math.random().toString(36).slice(2, 8)}`;

  /* ----------------------------------------------------------
   * Boot: wait until the deck has rendered once
   * -------------------------------------------------------- */
  function whenReady(fn) {
    // Always defer to a later tick so the rest of this module (its const/let
    // state declared further down) is fully initialized before init runs —
    // otherwise a ready Deck.data would run fn synchronously and hit a TDZ.
    if (Deck.data) { setTimeout(fn, 0); return; }
    const poll = setInterval(() => {
      if (Deck.data) { clearInterval(poll); setTimeout(fn, 0); }
    }, 50);
  }

  whenReady(() => {
    document.body.classList.add('editing');
    buildToolbar();
    buildModal();
    buildAnnotPalette();
    Deck.onChange((event) => {
      if (event === 'render' || event === 'navigate') decorateCurrentSlide();
    });
    bindContentEditing();
    bindAnnotations();
    offerDraftRestore();
    decorateCurrentSlide();
    Deck.fitStage();
  });

  /* ----------------------------------------------------------
   * Toolbar
   * -------------------------------------------------------- */
  function buildToolbar() {
    const bar = document.createElement('div');
    bar.className = 'editor-bar';
    bar.innerHTML = `
      <div class="bar-group">
        <span class="bar-label">Slide</span>
        <button data-act="slide-add" title="Add a slide after this one">+ New</button>
        <button data-act="slide-dup" title="Duplicate this slide">Duplicate</button>
        <button data-act="slide-left" title="Move slide earlier">&#8592;</button>
        <button data-act="slide-right" title="Move slide later">&#8594;</button>
        <button data-act="slide-del" class="danger" title="Delete this slide">Delete</button>
      </div>
      <div class="bar-group">
        <span class="bar-label">Block</span>
        <button data-act="block-text" title="Add a text block">+ Text</button>
        <button data-act="block-comp" title="Add an interactive component">+ Component</button>
      </div>
      <div class="bar-group">
        <span class="bar-label">List</span>
        <button data-fmt="bullets" title="Bulleted list (turn the current line into a bullet)">&bull; List</button>
        <button data-fmt="numbers" title="Numbered list">1. List</button>
        <button data-fmt="indent" title="Indent / nest (or press Tab in a list)">&#8677;</button>
        <button data-fmt="outdent" title="Outdent (or press Shift+Tab in a list)">&#8676;</button>
      </div>
      <div class="bar-group">
        <span class="bar-label">Draw</span>
        <button data-tool="select" title="Select, move or delete a mark">&#9673;</button>
        <button data-tool="pen" title="Freehand pen">&#9998;</button>
        <button data-tool="line" title="Line / arrow">&#8599;</button>
        <button data-tool="text" title="Text label — click to place, then drag">T</button>
        <button data-act="annot-undo" title="Undo last mark on this slide">&#8630;</button>
        <button data-act="annot-clear" class="danger" title="Clear all marks on this slide">Clear</button>
      </div>
      <div class="bar-group bar-right">
        <span class="save-status" id="save-status">All changes saved</span>
        <button data-act="save" class="primary" title="Save to content/slides.json (or download if no save server)">Save</button>
        <button data-act="export" title="Download slides.json">Export</button>
        <button data-act="exit" title="Leave edit mode">Done</button>
      </div>`;
    document.body.appendChild(bar);

    bar.addEventListener('click', (e) => {
      const toolBtn = e.target.closest && e.target.closest('[data-tool]');
      if (toolBtn) { setTool(toolBtn.dataset.tool); return; }
      const act = e.target.dataset && e.target.dataset.act;
      if (!act) return;
      const actions = {
        'slide-add': addSlide,
        'slide-dup': duplicateSlide,
        'slide-left': () => moveSlide(-1),
        'slide-right': () => moveSlide(1),
        'slide-del': deleteSlide,
        'block-text': addTextBlock,
        'block-comp': addComponentBlock,
        'annot-undo': annotUndo,
        'annot-clear': annotClear,
        'save': save,
        'export': exportFile,
        'exit': exitEditMode,
      };
      actions[act] && actions[act]();
    });

    // Formatting buttons act on the focused text block. Use mousedown +
    // preventDefault so the caret/selection in the editable is not lost
    // when the button takes the click.
    bar.addEventListener('mousedown', (e) => {
      const btn = e.target.closest && e.target.closest('[data-fmt]');
      if (!btn) return;
      e.preventDefault();
      applyFormat(btn.dataset.fmt);
    });
  }

  /* ==========================================================
   * Annotation tools: freehand pen, line/arrow, movable text.
   * Marks live in slide.annotations (stage coords) and render
   * through Deck; here we handle the drawing/selection UX.
   * ======================================================== */
  const AN_COLORS = ['rgb(29, 61, 99)', 'rgb(206, 38, 30)', 'rgb(87, 114, 145)', 'rgb(87, 129, 69)', 'rgb(230, 159, 0)'];
  let tool = null;                       // null | 'select' | 'pen' | 'line' | 'text'
  let anStyle = { color: AN_COLORS[0], width: 3.5, size: 28, arrow: true };
  let selectedAid = null;
  let drawState = null;                  // transient pen/line drawing
  let dragState = null;                  // transient select-drag
  const anId = () => 'a-' + Math.random().toString(36).slice(2, 8);

  function activeSvg() { return document.querySelector('.slide.active .slide-annot'); }
  function annots() {
    const s = Deck.data.slides[Deck.current];
    if (!s.annotations) s.annotations = [];
    return s.annotations;
  }
  function findAnnot(id) { return annots().find(a => a.id === id); }

  // client coords -> stage (1280x720) coords via the SVG's screen matrix
  function toStage(e, svg) {
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const m = svg.getScreenCTM(); if (!m) return null;
    const p = pt.matrixTransform(m.inverse());
    return { x: p.x, y: p.y };
  }
  function toScreen(x, y, svg) {
    const pt = svg.createSVGPoint(); pt.x = x; pt.y = y;
    const m = svg.getScreenCTM();
    const p = pt.matrixTransform(m);
    return { x: p.x, y: p.y, scale: m.a };
  }

  function setTool(t) {
    commitTextEdit();
    tool = (tool === t) ? null : t;      // clicking the active tool turns it off
    selectedAid = null;
    document.querySelectorAll('.editor-bar [data-tool]').forEach(b =>
      b.classList.toggle('tool-on', b.dataset.tool === tool));
    applyToolToActiveSvg();
    updatePalette();
    if (tool && tool !== 'select') blurEditable();
  }

  function blurEditable() { const a = document.activeElement; if (a && a.blur) a.blur(); }

  function applyToolToActiveSvg() {
    document.querySelectorAll('.slide-annot').forEach(s => {
      s.classList.remove('tool-active', 't-pen', 't-line', 't-text', 't-select');
    });
    const svg = activeSvg();
    if (svg && tool) { svg.classList.add('tool-active', 't-' + tool); }
    drawSelection();
  }

  /* ---- palette (colours / width / text size / arrow) ---- */
  function buildAnnotPalette() {
    const p = document.createElement('div');
    p.className = 'annot-palette';
    p.hidden = true;
    p.innerHTML = `
      <div class="ap-row ap-colors">${AN_COLORS.map(c =>
        `<button class="ap-sw" data-color="${c}" style="background:${c}"></button>`).join('')}</div>
      <div class="ap-row ap-widths" data-group="width">
        <button data-width="2">&#183;</button><button data-width="3.5">&#8226;</button><button data-width="6">&#9679;</button>
      </div>
      <div class="ap-row ap-sizes" data-group="size">
        <button data-size="20">S</button><button data-size="28">M</button><button data-size="40">L</button>
      </div>
      <div class="ap-row ap-arrow" data-group="arrow">
        <label><input type="checkbox" id="ap-arrow-cb" checked> arrowhead</label>
      </div>`;
    document.body.appendChild(p);
    p.addEventListener('click', (e) => {
      const sw = e.target.closest('[data-color]');
      if (sw) { anStyle.color = sw.dataset.color; applyStyleToSelection('color', sw.dataset.color); updatePalette(); return; }
      const w = e.target.closest('[data-width]');
      if (w) { anStyle.width = parseFloat(w.dataset.width); applyStyleToSelection('width', anStyle.width); updatePalette(); return; }
      const s = e.target.closest('[data-size]');
      if (s) { anStyle.size = parseInt(s.dataset.size, 10); applyStyleToSelection('size', anStyle.size); updatePalette(); return; }
    });
    p.querySelector('#ap-arrow-cb').addEventListener('change', (e) => {
      anStyle.arrow = e.target.checked; applyStyleToSelection('arrow', anStyle.arrow);
    });
  }

  function applyStyleToSelection(key, val) {
    if (!selectedAid) return;
    const a = findAnnot(selectedAid); if (!a) return;
    if (key === 'size' && a.type !== 'text') return;
    if (key === 'arrow' && a.type !== 'line') return;
    a[key] = val; Deck.renderAnnotations(); drawSelection(); markDirty();
  }

  function updatePalette() {
    const p = $('.annot-palette'); if (!p) return;
    const show = tool === 'pen' || tool === 'line' || tool === 'text';
    p.hidden = !show;
    if (!show) return;
    p.querySelector('.ap-widths').style.display = (tool === 'pen' || tool === 'line') ? '' : 'none';
    p.querySelector('.ap-sizes').style.display = (tool === 'text') ? '' : 'none';
    p.querySelector('.ap-arrow').style.display = (tool === 'line') ? '' : 'none';
    p.querySelectorAll('.ap-sw').forEach(b => b.classList.toggle('on', b.dataset.color === anStyle.color));
    p.querySelectorAll('[data-width]').forEach(b => b.classList.toggle('on', parseFloat(b.dataset.width) === anStyle.width));
    p.querySelectorAll('[data-size]').forEach(b => b.classList.toggle('on', parseInt(b.dataset.size, 10) === anStyle.size));
    p.querySelector('#ap-arrow-cb').checked = anStyle.arrow;
  }

  /* ---- pointer handling for drawing / selecting ---- */
  function bindAnnotations() {
    document.addEventListener('pointerdown', onAnnotDown);
    document.addEventListener('pointermove', onAnnotMove);
    document.addEventListener('pointerup', onAnnotUp);
    document.addEventListener('dblclick', onAnnotDblClick);
    document.addEventListener('keydown', (e) => {
      if (!tool) return;
      if (e.key === 'Escape') { setTool(tool); }               // toggle off
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedAid
        && !/^(INPUT|TEXTAREA)$/.test(e.target.tagName) && !e.target.isContentEditable) {
        e.preventDefault(); deleteSelected();
      }
    });
  }

  function onAnnotDown(e) {
    if (!tool) return;
    const svg = activeSvg(); if (!svg) return;
    if (e.target.closest('.editor-bar') || e.target.closest('.annot-palette') || e.target.closest('.annot-textedit')) return;
    const p = toStage(e, svg); if (!p || p.x < 0 || p.x > Deck.STAGE_W || p.y < 0 || p.y > Deck.STAGE_H) return;
    e.preventDefault();

    if (tool === 'pen') {
      drawState = { type: 'pen', pts: [[r1(p.x), r1(p.y)]], el: mkTemp('path') };
      drawState.el.setAttribute('fill', 'none');
      strokeTemp(drawState.el);
    } else if (tool === 'line') {
      drawState = { type: 'line', x1: r1(p.x), y1: r1(p.y), x2: r1(p.x), y2: r1(p.y), el: mkTemp('line') };
      strokeTemp(drawState.el);
      setLine(drawState.el, drawState);
    } else if (tool === 'text') {
      openTextEditor(null, r1(p.x), r1(p.y));
    } else if (tool === 'select') {
      const hit = e.target.closest('[data-aid]');
      if (hit) {
        selectedAid = hit.dataset.aid;
        const a = findAnnot(selectedAid);
        if (a) { syncStyleFrom(a); updatePalette(); }
        dragState = { last: p };
      } else { selectedAid = null; }
      drawSelection();
    }
  }

  function onAnnotMove(e) {
    if (!drawState && !dragState) return;
    const svg = activeSvg(); if (!svg) return;
    const p = toStage(e, svg); if (!p) return;
    if (drawState && drawState.type === 'pen') {
      drawState.pts.push([r1(p.x), r1(p.y)]);
      drawState.el.setAttribute('d', Deck.penPath(drawState.pts));
    } else if (drawState && drawState.type === 'line') {
      drawState.x2 = r1(p.x); drawState.y2 = r1(p.y); setLine(drawState.el, drawState);
    } else if (dragState && selectedAid) {
      const dx = p.x - dragState.last.x, dy = p.y - dragState.last.y;
      translateAnnot(findAnnot(selectedAid), dx, dy);
      dragState.last = p;
      Deck.renderAnnotations(); drawSelection();
    }
  }

  function onAnnotUp() {
    if (drawState) {
      if (drawState.type === 'pen' && drawState.pts.length > 1) {
        annots().push({ id: anId(), type: 'pen', pts: drawState.pts, color: anStyle.color, width: anStyle.width });
        commitAnnot();
      } else if (drawState.type === 'line' && Math.hypot(drawState.x2 - drawState.x1, drawState.y2 - drawState.y1) > 4) {
        annots().push({ id: anId(), type: 'line', x1: drawState.x1, y1: drawState.y1, x2: drawState.x2, y2: drawState.y2, arrow: anStyle.arrow, color: anStyle.color, width: anStyle.width });
        commitAnnot();
      }
      if (drawState.el && drawState.el.parentNode) drawState.el.parentNode.removeChild(drawState.el);
      drawState = null;
    }
    if (dragState) { dragState = null; markDirty(); }
  }

  function onAnnotDblClick(e) {
    if (tool !== 'select') return;
    const t = e.target.closest('.annot-text[data-aid]');
    if (!t) return;
    const a = findAnnot(t.dataset.aid); if (!a) return;
    openTextEditor(a.id, a.x, a.y);
  }

  // temp elements for live preview
  function mkTemp(tag) { const svg = activeSvg(); const el = document.createElementNS(Deck.SVG_NS, tag); svg.appendChild(el); return el; }
  function strokeTemp(el) {
    el.setAttribute('stroke', anStyle.color); el.setAttribute('stroke-width', anStyle.width);
    el.setAttribute('stroke-linecap', 'round'); el.setAttribute('stroke-linejoin', 'round'); el.setAttribute('fill', 'none');
  }
  function setLine(el, s) { el.setAttribute('x1', s.x1); el.setAttribute('y1', s.y1); el.setAttribute('x2', s.x2); el.setAttribute('y2', s.y2); }
  function r1(v) { return Math.round(v * 10) / 10; }

  function translateAnnot(a, dx, dy) {
    if (!a) return;
    if (a.type === 'text') { a.x = r1(a.x + dx); a.y = r1(a.y + dy); }
    else if (a.type === 'line') { a.x1 = r1(a.x1 + dx); a.y1 = r1(a.y1 + dy); a.x2 = r1(a.x2 + dx); a.y2 = r1(a.y2 + dy); }
    else if (a.type === 'pen') { a.pts = a.pts.map(pt => [r1(pt[0] + dx), r1(pt[1] + dy)]); }
  }
  function syncStyleFrom(a) {
    if (a.color) anStyle.color = a.color;
    if (a.type !== 'text' && a.width) anStyle.width = a.width;
    if (a.type === 'text' && a.size) anStyle.size = a.size;
    if (a.type === 'line') anStyle.arrow = !!a.arrow;
  }

  function commitAnnot() { Deck.renderAnnotations(); drawSelection(); markDirty(); }

  function deleteSelected() {
    const i = annots().findIndex(a => a.id === selectedAid);
    if (i >= 0) { annots().splice(i, 1); selectedAid = null; commitAnnot(); }
  }
  function annotUndo() {
    const list = annots(); if (!list.length) { toast('No marks to undo on this slide.'); return; }
    list.pop(); selectedAid = null; commitAnnot();
  }
  function annotClear() {
    if (!annots().length) { toast('No marks on this slide.'); return; }
    confirmDialog('Clear all drawn marks on this slide?', () => {
      Deck.data.slides[Deck.current].annotations = []; selectedAid = null; commitAnnot();
    });
  }

  // dashed selection box around the selected mark
  function drawSelection() {
    const svg = activeSvg(); if (!svg) return;
    const old = svg.querySelector('.annot-selbox'); if (old) old.remove();
    if (!selectedAid || tool !== 'select') return;
    const el = svg.querySelector(`[data-aid="${selectedAid}"]`); if (!el) return;
    let b; try { b = el.getBBox(); } catch (_) { return; }
    const pad = 6;
    const rect = document.createElementNS(Deck.SVG_NS, 'rect');
    rect.setAttribute('class', 'annot-selbox');
    rect.setAttribute('x', b.x - pad); rect.setAttribute('y', b.y - pad);
    rect.setAttribute('width', b.width + pad * 2); rect.setAttribute('height', b.height + pad * 2);
    svg.appendChild(rect);
  }

  /* ---- text place / edit via a positioned input ---- */
  let textEdit = null;   // { input, aid, isNew }
  function openTextEditor(aid, x, y) {
    commitTextEdit();
    const svg = activeSvg(); if (!svg) return;
    let a = aid ? findAnnot(aid) : null;
    let isNew = false;
    if (!a) { a = { id: anId(), type: 'text', x, y, text: '', color: anStyle.color, size: anStyle.size }; annots().push(a); isNew = true; Deck.renderAnnotations(); }
    const scr = toScreen(a.x, a.y, svg);
    const input = document.createElement('input');
    input.className = 'annot-textedit'; input.type = 'text'; input.value = a.text || '';
    input.style.left = scr.x + 'px'; input.style.top = scr.y + 'px';
    input.style.font = `${a.size * scr.scale}px/1.1 Lato, sans-serif`;
    input.style.color = a.color;
    document.body.appendChild(input);
    input.focus();
    textEdit = { input, aid: a.id, isNew };
    // hide the SVG copy while editing to avoid double image
    const svgEl = svg.querySelector(`[data-aid="${a.id}"]`); if (svgEl) svgEl.style.opacity = '0';
    input.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter') { ev.preventDefault(); commitTextEdit(); }
      else if (ev.key === 'Escape') { ev.preventDefault(); cancelTextEdit(); }
    });
    input.addEventListener('blur', commitTextEdit);
  }
  function commitTextEdit() {
    if (!textEdit) return;
    const { input, aid, isNew } = textEdit; textEdit = null;
    const a = findAnnot(aid);
    const val = input.value.trim();
    input.remove();
    if (a) {
      if (!val) { const i = annots().findIndex(x => x.id === aid); if (i >= 0) annots().splice(i, 1); }
      else { a.text = val; }
    }
    Deck.renderAnnotations();
    if (a && input.value.trim()) { selectedAid = aid; if (tool === 'text') setTool('select'); else drawSelection(); }
    markDirty();
  }
  function cancelTextEdit() {
    if (!textEdit) return;
    const { input, aid, isNew } = textEdit; textEdit = null;
    if (isNew) { const i = annots().findIndex(x => x.id === aid); if (i >= 0) annots().splice(i, 1); }
    input.remove(); Deck.renderAnnotations(); markDirty();
  }

  /* ----------------------------------------------------------
   * List / indent formatting inside editable text blocks
   * -------------------------------------------------------- */
  let lastEditable = null;

  function activeEditable() {
    const a = document.activeElement;
    if (a && a.classList && a.classList.contains('block-html')) return a;
    // Fall back to the most recently focused editable (covers the moment
    // right after a toolbar button is pressed).
    return lastEditable && document.body.contains(lastEditable) ? lastEditable : null;
  }

  function caretInListItem() {
    const sel = window.getSelection();
    if (!sel || !sel.anchorNode) return false;
    let n = sel.anchorNode;
    while (n && n !== document.body) {
      if (n.nodeType === 1 && n.tagName === 'LI') return true;
      n = n.parentNode;
    }
    return false;
  }

  function applyFormat(fmt) {
    const el = activeEditable();
    if (!el) { toast('Click into a text block first, then use the List buttons.'); return; }
    const cmd = {
      bullets: 'insertUnorderedList',
      numbers: 'insertOrderedList',
      indent: 'indent',
      outdent: 'outdent',
    }[fmt];
    if (!cmd) return;
    document.execCommand(cmd, false, null);
    syncEditable(el);
  }

  // Write an editable block's current HTML back into the data model.
  function syncEditable(el) {
    const block = findBlock(el.dataset.blockId, currentBlocks());
    if (!block) return;
    const clone = el.cloneNode(true);
    clone.querySelectorAll('.block-controls').forEach(c => c.remove());
    block.html = clone.innerHTML;
    markDirty();
  }

  /* ----------------------------------------------------------
   * Slide operations
   * -------------------------------------------------------- */
  function addSlide() {
    const slide = {
      id: newId('slide'),
      layout: 'default',
      blocks: [
        { id: newId('b'), type: 'html', html: '<p class="kicker">Section</p>' },
        { id: newId('b'), type: 'html', html: '<h2>New slide</h2>' },
        { id: newId('b'), type: 'html', html: '<p>Click any text to edit it.</p>' },
      ],
      notes: '',
    };
    Deck.data.slides.splice(Deck.current + 1, 0, slide);
    markDirty();
    Deck.renderAll();
    Deck.goTo(Deck.current + 1);
  }

  function duplicateSlide() {
    const copy = JSON.parse(JSON.stringify(Deck.data.slides[Deck.current]));
    copy.id = newId('slide');
    reassignIds(copy.blocks);
    Deck.data.slides.splice(Deck.current + 1, 0, copy);
    markDirty();
    Deck.renderAll();
    Deck.goTo(Deck.current + 1);
  }

  function reassignIds(blocks) {
    for (const b of blocks || []) {
      b.id = newId('b');
      if (b.type === 'row') reassignIds(b.children);
    }
  }

  function moveSlide(dir) {
    const i = Deck.current;
    const j = i + dir;
    const slides = Deck.data.slides;
    if (j < 0 || j >= slides.length) return;
    [slides[i], slides[j]] = [slides[j], slides[i]];
    markDirty();
    Deck.renderAll();
    Deck.goTo(j);
  }

  function deleteSlide() {
    if (Deck.data.slides.length === 1) { toast('A deck needs at least one slide.'); return; }
    confirmDialog('Delete this slide?', () => {
      Deck.data.slides.splice(Deck.current, 1);
      markDirty();
      Deck.renderAll();
    });
  }

  /* ----------------------------------------------------------
   * Block operations (top-level blocks of the current slide)
   * -------------------------------------------------------- */
  function currentBlocks() { return Deck.data.slides[Deck.current].blocks; }

  function addTextBlock() {
    currentBlocks().push({ id: newId('b'), type: 'html', html: '<p>New text — click to edit.</p>' });
    markDirty();
    Deck.remountCurrentSlide();
  }

  function addComponentBlock() {
    const names = [...Deck.registry.keys()];
    if (names.length === 0) { toast('No components registered — add one to components/ first.'); return; }
    openModal({
      title: 'Add component',
      body: `
        <label>Component
          <select id="m-comp">${names.map(n => `<option>${Deck.escapeHtml(n)}</option>`).join('')}</select>
        </label>
        <label>Props (JSON)
          <textarea id="m-props" rows="6" spellcheck="false">{}</textarea>
        </label>
        <label>Height in px (blank = fill remaining space)
          <input id="m-height" type="number" min="80" step="10" placeholder="auto">
        </label>`,
      confirm: 'Add',
      onConfirm: () => {
        let props;
        try { props = JSON.parse($('#m-props').value || '{}'); }
        catch { toast('Props must be valid JSON.'); return false; }
        const block = { id: newId('b'), type: 'component', component: $('#m-comp').value, props };
        const h = parseInt($('#m-height').value, 10);
        if (!Number.isNaN(h)) block.height = h;
        currentBlocks().push(block);
        markDirty();
        Deck.remountCurrentSlide();
        return true;
      },
    });
  }

  function findTopLevelIndex(blockId) {
    return currentBlocks().findIndex(b => b.id === blockId);
  }

  function moveBlock(blockId, dir) {
    const blocks = currentBlocks();
    const i = findTopLevelIndex(blockId);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= blocks.length) return;
    [blocks[i], blocks[j]] = [blocks[j], blocks[i]];
    markDirty();
    Deck.remountCurrentSlide();
  }

  function deleteBlock(blockId) {
    const i = findTopLevelIndex(blockId);
    if (i < 0) { toast('Blocks inside a row are managed in slides.json.'); return; }
    currentBlocks().splice(i, 1);
    markDirty();
    Deck.remountCurrentSlide();
  }

  function editComponentBlock(block) {
    openModal({
      title: `Edit &ldquo;${Deck.escapeHtml(block.component)}&rdquo;`,
      body: `
        <label>Props (JSON)
          <textarea id="m-props" rows="10" spellcheck="false">${Deck.escapeHtml(JSON.stringify(block.props || {}, null, 2))}</textarea>
        </label>
        <label>Height in px (blank = fill remaining space)
          <input id="m-height" type="number" min="80" step="10" value="${block.height || ''}" placeholder="auto">
        </label>`,
      confirm: 'Apply',
      onConfirm: () => {
        try { block.props = JSON.parse($('#m-props').value || '{}'); }
        catch { toast('Props must be valid JSON.'); return false; }
        const h = parseInt($('#m-height').value, 10);
        if (Number.isNaN(h)) delete block.height; else block.height = h;
        markDirty();
        Deck.remountCurrentSlide();
        return true;
      },
    });
  }

  function findBlock(blockId, blocks) {
    for (const b of blocks || []) {
      if (b.id === blockId) return b;
      if (b.type === 'row') {
        const hit = findBlock(blockId, b.children);
        if (hit) return hit;
      }
    }
    return null;
  }

  /* ----------------------------------------------------------
   * Slide decoration: make text editable, attach block controls
   * -------------------------------------------------------- */
  function decorateCurrentSlide() {
    const slideEl = document.querySelector('.slide.active');
    if (!slideEl) return;

    slideEl.querySelectorAll('.block-html').forEach(el => {
      el.setAttribute('contenteditable', 'true');
    });

    // Controls on top-level blocks only; nested (row) blocks keep
    // text editing + a props button, but structure lives in JSON.
    slideEl.querySelectorAll('.slide-body > .block').forEach(el => {
      if (el.querySelector(':scope > .block-controls')) return;
      const isComponent = el.classList.contains('block-component');
      const strip = document.createElement('div');
      strip.className = 'block-controls';
      strip.setAttribute('contenteditable', 'false');
      strip.innerHTML = `
        ${isComponent ? '<button data-bact="props" title="Edit component props">Props</button>' : ''}
        <button data-bact="up" title="Move block up">&#8593;</button>
        <button data-bact="down" title="Move block down">&#8595;</button>
        <button data-bact="del" class="danger" title="Delete block">&#10005;</button>`;
      el.appendChild(strip);
    });

    slideEl.querySelectorAll('.block-row .block-component').forEach(el => {
      if (el.querySelector(':scope > .block-controls')) return;
      const strip = document.createElement('div');
      strip.className = 'block-controls';
      strip.innerHTML = `<button data-bact="props" title="Edit component props">Props</button>`;
      el.appendChild(strip);
    });

    applyToolToActiveSvg();
  }

  document.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-bact]');
    if (!btn) return;
    const blockEl = btn.closest('.block');
    const blockId = blockEl.dataset.blockId;
    const act = btn.dataset.bact;
    if (act === 'up') moveBlock(blockId, -1);
    else if (act === 'down') moveBlock(blockId, 1);
    else if (act === 'del') deleteBlock(blockId);
    else if (act === 'props') {
      const block = findBlock(blockId, currentBlocks());
      if (block) editComponentBlock(block);
    }
  });

  /* ----------------------------------------------------------
   * Text editing: sync contenteditable back into the data model
   * -------------------------------------------------------- */
  function bindContentEditing() {
    document.addEventListener('input', (e) => {
      const el = e.target.closest && e.target.closest('.block-html[contenteditable]');
      if (!el) return;
      syncEditable(el);
    });

    // Remember the focused editable so the List buttons know their target.
    document.addEventListener('focusin', (e) => {
      const el = e.target.closest && e.target.closest('.block-html[contenteditable]');
      if (el) lastEditable = el;
    });

    // Tab / Shift+Tab nest and un-nest, but only inside a list — elsewhere
    // Tab keeps its normal behaviour. Capture phase so we act before the
    // browser moves focus.
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Tab') return;
      const el = e.target.closest && e.target.closest('.block-html[contenteditable]');
      if (!el || !caretInListItem()) return;
      e.preventDefault();
      document.execCommand(e.shiftKey ? 'outdent' : 'indent', false, null);
      syncEditable(el);
    }, true);
  }

  /* ----------------------------------------------------------
   * Persistence: save (POST /save -> fallback download) + drafts
   * -------------------------------------------------------- */
  function serialize() { return JSON.stringify(Deck.data, null, 2) + '\n'; }

  async function save() {
    const body = serialize();
    try {
      const res = await fetch('/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      markClean('Saved to content/slides.json');
      toast('Saved to content/slides.json');
    } catch {
      downloadFile(body);
      markClean('Exported — replace content/slides.json with the download');
      toast('No save server here — downloaded slides.json instead. Replace content/slides.json with it.');
    }
  }

  function exportFile() {
    downloadFile(serialize());
    markClean('Exported — replace content/slides.json with the download');
  }

  function downloadFile(text) {
    const blob = new Blob([text], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'slides.json';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function markDirty() {
    dirty = true;
    setStatus('Unsaved changes', true);
    clearTimeout(draftTimer);
    draftTimer = setTimeout(() => {
      try {
        localStorage.setItem(DRAFT_KEY, JSON.stringify({ savedAt: Date.now(), data: Deck.data }));
      } catch (e) { console.warn('Could not store draft:', e); }
    }, 400);
  }

  function markClean(msg) {
    dirty = false;
    localStorage.removeItem(DRAFT_KEY);
    setStatus(msg || 'All changes saved', false);
  }

  function setStatus(text, isDirty) {
    const el = $('#save-status');
    if (!el) return;
    el.textContent = text;
    el.classList.toggle('dirty', !!isDirty);
  }

  function offerDraftRestore() {
    let draft;
    try { draft = JSON.parse(localStorage.getItem(DRAFT_KEY)); } catch { /* ignore */ }
    if (!draft || !draft.data) return;
    if (JSON.stringify(draft.data) === JSON.stringify(Deck.data)) {
      localStorage.removeItem(DRAFT_KEY);
      return;
    }
    const bar = document.createElement('div');
    bar.className = 'draft-bar';
    const when = new Date(draft.savedAt).toLocaleString();
    bar.innerHTML = `
      <span>Unsaved draft from ${Deck.escapeHtml(when)} differs from the file on disk.</span>
      <button id="draft-restore">Restore draft</button>
      <button id="draft-discard">Use file version</button>`;
    document.body.appendChild(bar);
    $('#draft-restore').addEventListener('click', () => {
      Object.assign(Deck.data, draft.data);
      markDirty();
      Deck.renderAll();
      bar.remove();
      toast('Draft restored — remember to save.');
    });
    $('#draft-discard').addEventListener('click', () => {
      localStorage.removeItem(DRAFT_KEY);
      bar.remove();
    });
  }

  function exitEditMode() {
    const leave = () => {
      const url = new URL(location.href);
      url.searchParams.delete('edit');
      location.href = url.toString();
    };
    if (dirty) confirmDialog('You have unsaved changes. Leave anyway? (Your draft is kept in this browser.)', leave);
    else leave();
  }

  window.addEventListener('beforeunload', (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  /* ----------------------------------------------------------
   * Modal + toast + confirm
   * -------------------------------------------------------- */
  let modalConfirmFn = null;

  function buildModal() {
    const overlay = document.createElement('div');
    overlay.className = 'editor-modal';
    overlay.id = 'editor-modal';
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="modal-card">
        <h3 id="modal-title"></h3>
        <div class="modal-body" id="modal-body"></div>
        <div class="modal-actions">
          <button id="modal-cancel">Cancel</button>
          <button id="modal-confirm" class="primary"></button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    $('#modal-cancel').addEventListener('click', closeModal);
    $('#modal-confirm').addEventListener('click', () => {
      if (!modalConfirmFn || modalConfirmFn() !== false) closeModal();
    });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !overlay.hidden) closeModal();
    });
  }

  function openModal({ title, body, confirm, onConfirm }) {
    $('#modal-title').innerHTML = title;
    $('#modal-body').innerHTML = body;
    $('#modal-confirm').textContent = confirm || 'OK';
    modalConfirmFn = onConfirm;
    $('#editor-modal').hidden = false;
  }

  function closeModal() {
    $('#editor-modal').hidden = true;
    modalConfirmFn = null;
  }

  function confirmDialog(message, onYes) {
    openModal({
      title: 'Confirm',
      body: `<p>${Deck.escapeHtml(message)}</p>`,
      confirm: 'Yes',
      onConfirm: () => { onYes(); return true; },
    });
  }

  let toastTimer = null;
  function toast(msg) {
    let el = $('#editor-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'editor-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('show'), 3200);
  }
})();
