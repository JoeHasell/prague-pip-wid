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
    if (Deck.data) { fn(); return; }
    const poll = setInterval(() => {
      if (Deck.data) { clearInterval(poll); fn(); }
    }, 50);
  }

  whenReady(() => {
    document.body.classList.add('editing');
    buildToolbar();
    buildModal();
    Deck.onChange((event) => {
      if (event === 'render' || event === 'navigate') decorateCurrentSlide();
    });
    bindContentEditing();
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
      <div class="bar-group bar-right">
        <span class="save-status" id="save-status">All changes saved</span>
        <button data-act="save" class="primary" title="Save to content/slides.json (or download if no save server)">Save</button>
        <button data-act="export" title="Download slides.json">Export</button>
        <button data-act="exit" title="Leave edit mode">Done</button>
      </div>`;
    document.body.appendChild(bar);

    bar.addEventListener('click', (e) => {
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
        'save': save,
        'export': exportFile,
        'exit': exitEditMode,
      };
      actions[act] && actions[act]();
    });
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
      const block = findBlock(el.dataset.blockId, currentBlocks());
      if (!block) return;
      const clone = el.cloneNode(true);
      clone.querySelectorAll('.block-controls').forEach(c => c.remove());
      block.html = clone.innerHTML;
      markDirty();
    });
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
