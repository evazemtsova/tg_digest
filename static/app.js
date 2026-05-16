// Vacancy digest — client-side filtering, search, sort & infinite scroll.

const data = JSON.parse(document.getElementById('vacancies-data').textContent || '[]');
const byUid = new Map();

const state = {
  tab: '24h',
  location: 'all',
  grade: 'all',
  sort: 'date',
  mlOnly: false,
  query: '',
};

const root = document.getElementById('vacancies');
const visibleCountEl = document.getElementById('visible-count');

const FILTER_LABELS = {
  location: { all: 'Все', moscow: 'Москва', spb: 'СПб', regions: 'Регионы', remote: 'Remote' },
  grade:    { all: 'Все', Lead: 'Lead', Head: 'Head', Senior: 'Senior', Middle: 'Middle' },
  sort:     { date: 'По дате', grade: 'По грейду' },
};

const GRADE_ORDER = { Head: 5, Lead: 4, Senior: 3, Middle: 2, Junior: 1 };

// ---------- Helpers ----------
const HOUR = 3600 * 1000;

function ageHours(iso) { return (Date.now() - new Date(iso).getTime()) / HOUR; }

function relativeTime(iso) {
  const h = ageHours(iso);
  if (h < 1) return 'JUST NOW';
  if (h < 24) return `${Math.floor(h)}H AGO`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}D AGO`;
  if (d < 30) return `${Math.floor(d / 7)}W AGO`;
  return `${Math.floor(d / 30)}MO AGO`;
}

function vUid(v) { return `${v.channel_id}:${v.msg_id}`; }

function matchesLocation(v) {
  if (state.location === 'all') return true;
  if (state.location === 'remote') return v.remote === true;
  const loc = (v.location || '').toLowerCase();
  if (state.location === 'moscow') return loc.includes('моск') || loc.includes('moscow');
  if (state.location === 'spb') return loc.includes('спб') || loc.includes('петерб') || loc.includes('peters');
  if (state.location === 'regions') {
    if (v.remote) return false;
    if (!loc) return false;
    if (loc.includes('моск') || loc.includes('спб') || loc.includes('петерб')) return false;
    return true;
  }
  return true;
}

function matchesGrade(v) {
  if (state.grade === 'all') return true;
  return v.grade === state.grade;
}

function matchesTab(v) {
  if (state.tab === 'archive') return v.is_archived === true;
  if (v.is_archived) return false;
  const h = ageHours(v.date_iso);
  if (state.tab === '24h') return h <= 24;
  if (state.tab === '7d') return h <= 24 * 7;
  if (state.tab === '30d') return h <= 24 * 30;
  return false;
}

function matchesMl(v) { return state.mlOnly ? v.ml_ai === true : true; }

function matchesQuery(v) {
  if (!state.query) return true;
  const q = state.query.toLowerCase();
  const hay = [v.title, v.company, v.short_description, v.text, v.location, v.channel_username, v.channel_title]
    .filter(Boolean).join(' ').toLowerCase();
  return hay.includes(q);
}

function sortItems(arr) {
  const sorted = arr.slice();
  if (state.sort === 'date') {
    sorted.sort((a, b) => b.date_iso.localeCompare(a.date_iso));
  } else if (state.sort === 'grade') {
    sorted.sort((a, b) => {
      const ga = GRADE_ORDER[a.grade] || 0;
      const gb = GRADE_ORDER[b.grade] || 0;
      if (gb !== ga) return gb - ga;
      return b.date_iso.localeCompare(a.date_iso);
    });
  }
  return sorted;
}

function filtered() {
  const items = data.filter(v =>
    matchesTab(v) && matchesLocation(v) && matchesGrade(v) &&
    matchesMl(v) && matchesQuery(v)
  );
  return sortItems(items);
}

// Count items per tab (respecting all OTHER filters except tab itself).
function tabCount(tab) {
  return data.filter(v => {
    const prev = state.tab;
    state.tab = tab;
    const ok = matchesTab(v);
    state.tab = prev;
    return ok && matchesLocation(v) && matchesGrade(v) && matchesMl(v) && matchesQuery(v);
  }).length;
}

function updateTabCounts() {
  ['24h', '7d', '30d', 'archive'].forEach(t => {
    const el = document.querySelector(`[data-count="${t}"]`);
    if (el) el.textContent = tabCount(t);
  });
}

// ---------- Render ----------
function escapeHtml(s) {
  return (s == null ? '' : String(s))
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Render text with clickable links: applies TG entities (covers hidden links
// like "[here](url)") then linkifies remaining plain http(s) URLs by regex.
// JS strings are UTF-16, matching TG entity offset units — slice directly.
const URL_RE = /https?:\/\/[^\s<>()"']+[^\s<>()"'.,;:!?]/g;

function safeHref(url) {
  const u = String(url || '').trim();
  return /^https?:\/\//i.test(u) ? u : '#';
}

function linkifyPlain(text) {
  let out = '';
  let last = 0;
  for (const m of text.matchAll(URL_RE)) {
    out += escapeHtml(text.slice(last, m.index));
    const url = m[0];
    out += `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(url)}</a>`;
    last = m.index + url.length;
  }
  out += escapeHtml(text.slice(last));
  return out;
}

function renderTextWithLinks(text, entities) {
  if (!text) return '';
  const ents = (entities || [])
    .filter(e => (e.type === 'url' || e.type === 'text_url') && e.length > 0)
    .slice()
    .sort((a, b) => a.offset - b.offset);

  let out = '';
  let cursor = 0;
  for (const e of ents) {
    if (e.offset < cursor) continue; // skip overlaps
    if (e.offset > cursor) out += linkifyPlain(text.slice(cursor, e.offset));
    const visible = text.slice(e.offset, e.offset + e.length);
    const href = e.type === 'text_url' ? e.url : visible;
    out += `<a href="${escapeHtml(safeHref(href))}" target="_blank" rel="noopener">${escapeHtml(visible)}</a>`;
    cursor = e.offset + e.length;
  }
  out += linkifyPlain(text.slice(cursor));
  return out;
}

function tagList(v) {
  const tags = [];
  if (v.grade) tags.push(`<span class="tag tag-grade">${escapeHtml(v.grade)}</span>`);
  if (v.ml_ai) tags.push('<span class="tag tag-ml">ML/AI</span>');
  if (v.remote) tags.push('<span class="tag">Remote</span>');
  if (v.salary) tags.push(`<span class="tag">${escapeHtml(v.salary)}</span>`);
  return tags.join('');
}

function dupesButton(v) {
  const dupes = v.duplicates || [];
  if (!dupes.length) return '';
  const items = dupes.map(d => {
    const label = d.channel_title || d.channel_username || 'канал';
    return `<a href="${escapeHtml(d.link)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
  }).join('');
  return `<button class="btn-dupes" type="button" data-action="dupes">×${dupes.length}<span class="dupes-tooltip">${items}</span></button>`;
}

function renderCard(v, idx) {
  const uid = vUid(v);
  const channel = v.channel_username ? `@${v.channel_username}` : (v.channel_title || '');
  const company = v.company || 'не указана';
  const location = v.location || (v.remote ? 'Remote' : 'не указана');
  const num = String(idx + 1).padStart(2, '0');
  const isNew = v.is_new ? 'is-new' : '';

  return `
    <article class="vacancy ${isNew}" data-uid="${escapeHtml(uid)}" role="button" tabindex="0">
      <div class="v-num">${num}</div>
      <div class="v-body">
        ${v.is_new ? '<div class="v-tags-top"><span class="tag-new">NEW</span></div>' : ''}
        <h2 class="v-title">${escapeHtml(v.title || '')}</h2>
        <div class="v-meta">
          ${escapeHtml(company)} · ${escapeHtml(location)} · ${escapeHtml(channel)}
        </div>
        <p class="v-desc">${escapeHtml(v.short_description || '')}</p>
        <div class="v-tags">${tagList(v)}</div>
      </div>
      <div class="v-aside">
        <div class="v-time">${relativeTime(v.date_iso)}</div>
        ${dupesButton(v)}
      </div>
    </article>`;
}

// ---------- Infinite scroll ----------
const BATCH_SIZE = 20;
let currentItems = [];
let renderedCount = 0;
let scrollObserver = null;

function appendBatch() {
  const next = currentItems.slice(renderedCount, renderedCount + BATCH_SIZE);
  if (!next.length) {
    if (scrollObserver) scrollObserver.disconnect();
    document.getElementById('scroll-sentinel')?.remove();
    return;
  }
  const html = next.map((v, i) => renderCard(v, renderedCount + i)).join('');
  document.getElementById('scroll-sentinel')?.remove();
  root.insertAdjacentHTML('beforeend', html);
  renderedCount += next.length;
  if (renderedCount < currentItems.length) {
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.cssText = 'height:1px;';
    root.appendChild(sentinel);
    scrollObserver.observe(sentinel);
  }
}

function render() {
  currentItems = filtered();
  renderedCount = 0;
  visibleCountEl.textContent = currentItems.length;
  root.innerHTML = '';

  updateTabCounts();
  updateResetVisibility();

  if (!currentItems.length) {
    root.innerHTML = '<p class="empty">Ничего не найдено для текущих фильтров.</p>';
    return;
  }

  if (!scrollObserver) {
    scrollObserver = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) appendBatch();
    }, { rootMargin: '600px 0px' });
  } else {
    scrollObserver.disconnect();
  }
  appendBatch();
}

// ---------- Dropdowns ----------
function closeAllPopovers(except = null) {
  document.querySelectorAll('.filter-dropdown.is-open').forEach(d => {
    if (d !== except) d.classList.remove('is-open');
  });
}

function setFilterValue(filter, value) {
  state[filter] = value;
  const dropdown = document.querySelector(`[data-filter="${filter}"]`);
  const valueEl = dropdown.querySelector('.filter-value');
  valueEl.textContent = FILTER_LABELS[filter][value] || value;
  const isAllOrDate = value === 'all' || (filter === 'sort' && value === 'date');
  dropdown.classList.toggle('has-value', !isAllOrDate);
  dropdown.querySelectorAll('.popover-item').forEach(item => {
    item.classList.toggle('is-active', item.dataset.value === value);
  });
  dropdown.classList.remove('is-open');
}

document.querySelectorAll('.filter-dropdown').forEach(dropdown => {
  const trigger = dropdown.querySelector('.filter-trigger');
  trigger.addEventListener('click', (e) => {
    e.stopPropagation();
    const wasOpen = dropdown.classList.contains('is-open');
    closeAllPopovers();
    if (!wasOpen) dropdown.classList.add('is-open');
  });
  dropdown.querySelector('.filter-popover').addEventListener('click', e => {
    const item = e.target.closest('.popover-item');
    if (!item) return;
    const filter = dropdown.dataset.filter;
    setFilterValue(filter, item.dataset.value);
    render();
  });
});

document.addEventListener('click', () => closeAllPopovers());

// ---------- Tabs ----------
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    state.tab = btn.dataset.tab;
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('is-active', b === btn));
    render();
  });
});

// ---------- ML toggle ----------
document.getElementById('ml-toggle').addEventListener('change', e => {
  state.mlOnly = e.target.checked;
  render();
});

// ---------- Search ----------
let searchTimer = null;
document.getElementById('search-input').addEventListener('input', e => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.query = e.target.value.trim();
    render();
  }, 150);
});

// ---------- Reset ----------
function updateResetVisibility() {
  const active = state.location !== 'all' || state.grade !== 'all' ||
                 state.mlOnly || state.query || state.sort !== 'date';
  document.querySelector('.reset-btn').hidden = !active;
}

document.querySelector('.reset-btn').addEventListener('click', () => {
  setFilterValue('location', 'all');
  setFilterValue('grade', 'all');
  setFilterValue('sort', 'date');
  state.mlOnly = false;
  state.query = '';
  document.getElementById('ml-toggle').checked = false;
  document.getElementById('search-input').value = '';
  render();
});

// Card-level actions (event delegation).
root.addEventListener('click', e => {
  // Dupes tooltip — handle separately and don't open the modal.
  const dupesBtn = e.target.closest('[data-action="dupes"]');
  if (dupesBtn) {
    if (e.target.closest('a')) return; // link inside tooltip — let it through
    document.querySelectorAll('.btn-dupes.is-open').forEach(b => {
      if (b !== dupesBtn) b.classList.remove('is-open');
    });
    dupesBtn.classList.toggle('is-open');
    e.stopPropagation();
    return;
  }

  // Card click → open modal with full text.
  const card = e.target.closest('.vacancy');
  if (card) openModal(card.dataset.uid);
});

root.addEventListener('keydown', e => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const card = e.target.closest('.vacancy');
  if (!card) return;
  e.preventDefault();
  openModal(card.dataset.uid);
});

// Close dupes tooltip when clicking outside.
document.addEventListener('click', e => {
  if (!e.target.closest('.btn-dupes')) {
    document.querySelectorAll('.btn-dupes.is-open').forEach(b => b.classList.remove('is-open'));
  }
});

// ---------- Modal ----------
const overlayEl = document.getElementById('modal-overlay');
const modalContentEl = document.getElementById('modal-content');
const modalCloseEl = document.getElementById('modal-close');

function openModal(uid) {
  const v = byUid.get(uid);
  if (!v) return;
  modalContentEl.innerHTML = renderModalContent(v);
  overlayEl.hidden = false;
  document.body.classList.add('modal-open');
  modalCloseEl.focus();
}

function closeModal() {
  if (overlayEl.hidden) return;
  overlayEl.hidden = true;
  document.body.classList.remove('modal-open');
  modalContentEl.innerHTML = '';
}

function renderModalContent(v) {
  const channel = v.channel_username ? `@${v.channel_username}` : (v.channel_title || '');
  const company = v.company || 'не указана';
  const location = v.location || (v.remote ? 'Remote' : 'не указана');
  const date = new Date(v.date_iso);
  const dateStr = date.toLocaleString('ru-RU', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
  const dupes = (v.duplicates || []).map(d => {
    const label = d.channel_title || d.channel_username || 'канал';
    return `<a href="${escapeHtml(d.link)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`;
  }).join('');

  return `
    ${v.is_new ? '<div class="v-tags-top"><span class="tag-new">NEW</span></div>' : ''}
    <h2 class="modal-title" id="modal-title">${escapeHtml(v.title || '')}</h2>
    <div class="modal-meta">
      ${escapeHtml(company)} · ${escapeHtml(location)} · ${escapeHtml(channel)} · <span class="mono">${escapeHtml(dateStr)}</span>
    </div>
    <div class="v-tags modal-tags">${tagList(v)}</div>
    <pre class="modal-text">${renderTextWithLinks(v.text || '', v.entities)}</pre>
    <div class="modal-actions">
      <a class="btn-open" href="${escapeHtml(v.link)}" target="_blank" rel="noopener">Открыть в Telegram →</a>
    </div>
    ${dupes ? `<div class="modal-dupes"><div class="modal-dupes-label mono">также в:</div>${dupes}</div>` : ''}
  `;
}

modalCloseEl.addEventListener('click', closeModal);
overlayEl.addEventListener('click', e => {
  if (e.target === overlayEl) closeModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

// ---------- Boot ----------
function pickInitialTab() {
  const counts = {
    '24h': data.filter(v => !v.is_archived && ageHours(v.date_iso) <= 24).length,
    '7d':  data.filter(v => !v.is_archived && ageHours(v.date_iso) <= 24 * 7).length,
    '30d': data.filter(v => !v.is_archived && ageHours(v.date_iso) <= 24 * 30).length,
  };
  if (counts['24h']) return '24h';
  if (counts['7d']) return '7d';
  return '30d';
}

data.forEach(v => byUid.set(vUid(v), v));

const initialTab = pickInitialTab();
if (initialTab !== '24h') {
  state.tab = initialTab;
  document.querySelectorAll('.tab').forEach(b => {
    b.classList.toggle('is-active', b.dataset.tab === initialTab);
  });
}

render();
