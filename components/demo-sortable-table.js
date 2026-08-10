/* Demo component: sortable table. Click a column header to sort.
 *
 * Props:
 *   columns  [{ key, label, numeric?: true }, ...]
 *   rows     [{ key: value, ... }, ...]
 *   caption  string (optional)
 * Falls back to demo data when no props are given.
 */
Deck.registerComponent('demo-sortable-table', (el, props) => {
  const columns = props.columns || [
    { key: 'region', label: 'Region' },
    { key: 'value2015', label: '2015', numeric: true },
    { key: 'value2025', label: '2025', numeric: true },
    { key: 'change', label: 'Change', numeric: true },
  ];
  const rows = props.rows || [
    { region: 'East Asia', value2015: 61.2, value2025: 78.9, change: 17.7 },
    { region: 'South Asia', value2015: 34.5, value2025: 58.1, change: 23.6 },
    { region: 'Sub-Saharan Africa', value2015: 22.1, value2025: 39.4, change: 17.3 },
    { region: 'Latin America', value2015: 55.7, value2025: 71.3, change: 15.6 },
    { region: 'Europe', value2015: 79.8, value2025: 89.5, change: 9.7 },
    { region: 'North America', value2015: 76.2, value2025: 91.8, change: 15.6 },
  ];

  let sortKey = null;
  let sortDir = 1;

  el.innerHTML = `
    <style>
      .dst { height: 100%; overflow: auto; padding: 18px 22px; }
      .dst .caption { font: 700 16px var(--font-body); margin-bottom: 10px; color: var(--ink); }
      .dst table { width: 100%; border-collapse: collapse; font: 16px var(--font-body); }
      .dst th {
        text-align: left; font: 600 13px var(--font-body); text-transform: uppercase;
        letter-spacing: 0.06em; color: var(--muted); padding: 8px 12px;
        border-bottom: 2px solid var(--mid); cursor: pointer; user-select: none;
        white-space: nowrap;
      }
      .dst th:hover { color: var(--accent); }
      .dst th .arrow { font-size: 10px; margin-left: 4px; }
      .dst td { padding: 9px 12px; border-bottom: 1px solid var(--line); }
      .dst td.num, .dst th.num { text-align: right; font-variant-numeric: tabular-nums; }
      .dst tr:hover td { background: rgb(245, 247, 250); }
    </style>
    <div class="dst">
      ${props.caption ? `<div class="caption">${props.caption}</div>` : ''}
      <table>
        <thead><tr>${columns.map(c =>
          `<th class="${c.numeric ? 'num' : ''}" data-key="${c.key}">${c.label}<span class="arrow"></span></th>`
        ).join('')}</tr></thead>
        <tbody></tbody>
      </table>
    </div>`;

  const tbody = el.querySelector('tbody');

  function renderRows() {
    const sorted = [...rows];
    if (sortKey) {
      sorted.sort((a, b) => {
        const av = a[sortKey], bv = b[sortKey];
        return (typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))) * sortDir;
      });
    }
    tbody.innerHTML = sorted.map(r =>
      `<tr>${columns.map(c =>
        `<td class="${c.numeric ? 'num' : ''}">${c.numeric && typeof r[c.key] === 'number' ? r[c.key].toLocaleString() : r[c.key]}</td>`
      ).join('')}</tr>`
    ).join('');
    el.querySelectorAll('th').forEach(th => {
      th.querySelector('.arrow').textContent =
        th.dataset.key === sortKey ? (sortDir === 1 ? '\u25B2' : '\u25BC') : '';
    });
  }

  el.querySelectorAll('th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (sortKey === key) sortDir = -sortDir;
      else { sortKey = key; sortDir = 1; }
      renderRows();
    });
  });

  renderRows();
});
