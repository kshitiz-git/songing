// Top bar (search, account buttons) and the left library panel. Markup lives in index.html.
import { h, $, $$, tile, cover, debounce, plural } from './dom.js';
import { api } from './api.js';
import { store, on, setUser } from './store.js';
import { navigate, reload, loginUrl } from './router.js';
import { playlistModal } from './ui/playlistmodal.js';
import { toast } from './ui/toast.js';

const AUTH_ONLY = ['/liked', '/recent', '/uploads', '/upload'];

export function initShell() {
  initSearch();
  initDrawer();
  renderAccount();
  renderLibrary();
  on('auth', () => {
    renderAccount();
    renderLibrary();
  });
  on('playlists', renderLibrary);
  on('route', ({ path }) => {
    markCurrentLinks(path);
    closeDrawer();
  });
  $('#create-playlist').addEventListener('click', createPlaylist);
}

// ---------- account buttons ----------
function renderAccount() {
  const box = $('#topbar-auth');
  const u = store.user;
  if (!u) {
    box.replaceChildren(
      h('a', { class: 'auth-link', href: '/signup', text: 'Sign up' }),
      h('a', { class: 'btn btn-light', href: '/login', text: 'Log in' }),
    );
    return;
  }
  box.replaceChildren(
    h('span', { class: 'user-chip', title: `Logged in as ${u.username}` }, h('span', { class: 'avatar', 'aria-hidden': 'true', text: u.username.slice(0, 1).toUpperCase() }), h('span', { class: 'user-name', text: u.username })),
    h('button', { type: 'button', class: 'btn btn-ghost', id: 'logout', text: 'Log out', onclick: logout }),
  );
}

async function logout() {
  try {
    await api('/api/auth/logout/', { method: 'POST' });
  } catch (err) {
    toast(err.message, { kind: 'error' });
    return;
  }
  setUser(null);
  toast('Logged out');
  if (AUTH_ONLY.includes(location.pathname.replace(/\/$/, ''))) navigate('/');
  else reload();
}

// ---------- search box ----------
function initSearch() {
  const form = $('#search-form');
  const input = $('#search-input');
  const clear = $('#search-clear');

  const go = (q) => {
    const onSearch = location.pathname.replace(/\/$/, '') === '/search';
    navigate(q ? `/search?q=${encodeURIComponent(q)}` : '/search', { replace: onSearch, focus: false });
  };
  const debounced = debounce(go, 300);

  // The long placeholder is cut off on phones.
  const mobile = matchMedia('(max-width: 699.98px)');
  const setPlaceholder = () => (input.placeholder = mobile.matches ? 'Search' : 'What do you want to play?');
  setPlaceholder();
  mobile.addEventListener('change', setPlaceholder);

  input.addEventListener('input', () => {
    clear.hidden = !input.value;
    debounced(input.value.trim());
  });
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    debounced.cancel();
    go(input.value.trim());
  });
  clear.addEventListener('click', () => {
    input.value = '';
    clear.hidden = true;
    debounced.cancel();
    input.focus();
    if (location.pathname.replace(/\/$/, '') === '/search') go('');
  });
  on('route', ({ name, query }) => {
    if (name === 'search') {
      const q = query.get('q') || '';
      if (document.activeElement !== input && input.value !== q) input.value = q;
    } else if (input.value) {
      input.value = '';
    }
    clear.hidden = !input.value;
  });
}

// ---------- drawer (phones) ----------
function openDrawer() {
  document.body.classList.add('drawer-open');
  $('#drawer-toggle').setAttribute('aria-expanded', 'true');
  $('#drawer-backdrop').hidden = false;
  const first = $('#library a, #library button');
  if (first) first.focus({ preventScroll: true });
}
function closeDrawer() {
  if (!document.body.classList.contains('drawer-open')) return;
  document.body.classList.remove('drawer-open');
  $('#drawer-toggle').setAttribute('aria-expanded', 'false');
  $('#drawer-backdrop').hidden = true;
}
function initDrawer() {
  const toggle = $('#drawer-toggle');
  toggle.addEventListener('click', () => (document.body.classList.contains('drawer-open') ? closeDrawer() : openDrawer()));
  $('#drawer-backdrop').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.body.classList.contains('drawer-open')) {
      closeDrawer();
      toggle.focus();
    }
  });
  matchMedia('(max-width: 699.98px)').addEventListener('change', (e) => {
    if (!e.matches) closeDrawer();
  });
}

// ---------- library panel ----------
function libItem(href, art, name, sub) {
  return h(
    'li',
    {},
    h('a', { class: 'lib-item', href, 'data-nav': '' }, art, h('span', { class: 'lib-text' }, h('span', { class: 'lib-name', text: name }), h('span', { class: 'lib-sub', text: sub }))),
  );
}

async function createPlaylist() {
  if (!store.user) {
    navigate(loginUrl());
    return;
  }
  const pl = await playlistModal();
  if (pl) {
    toast(`Created ${pl.name}`);
    navigate(`/playlist/${pl.id}`);
  }
}

function renderLibrary() {
  const body = $('#lib-body');
  const quick = h(
    'ul',
    { class: 'lib-list lib-quick' },
    libItem('/', tile('home', '#2a2a2e', '#17171a', 'lib-art'), 'Home', 'Start here'),
    libItem('/search', tile('search', '#2a2a2e', '#17171a', 'lib-art'), 'Search', 'Find music'),
  );
  quick.classList.add('mobile-only');

  if (!store.user) {
    body.replaceChildren(
      quick,
      h(
        'div',
        { class: 'lib-card' },
        h('h3', { text: 'Your library lives here' }),
        h('p', { text: 'Log in to like songs, make playlists and upload your own tracks.' }),
        h('div', { class: 'lib-card-actions' }, h('a', { class: 'btn btn-light', href: '/login', text: 'Log in' }), h('a', { class: 'btn btn-outline', href: '/signup', text: 'Sign up' })),
      ),
    );
    markCurrentLinks(location.pathname);
    return;
  }

  const list = h(
    'ul',
    { class: 'lib-list' },
    libItem('/liked', tile('heartFill', '#5b3cc4', '#a78bfa', 'lib-art'), 'Liked Songs', 'Playlist'),
    libItem('/recent', tile('clock', '#0e6b5c', '#2fd566', 'lib-art'), 'Recently played', 'Your history'),
    libItem('/uploads', tile('note', '#9a3b1f', '#ffb454', 'lib-art'), 'My uploads', 'Songs you added'),
    libItem('/upload', tile('upload', '#2b3b55', '#5aa7ff', 'lib-art'), 'Upload a song', 'Add your own music'),
  );
  for (const p of store.playlists) {
    list.append(libItem(`/playlist/${p.id}`, cover(p, { kind: 'playlist', cls: 'lib-art' }), p.name, `Playlist · ${plural(p.song_count ?? 0, 'song')}`));
  }
  const parts = [quick, list];
  if (!store.playlists.length) {
    parts.push(
      h(
        'div',
        { class: 'lib-card' },
        h('h3', { text: 'Create your first playlist' }),
        h('p', { text: 'It is easy. Name it, then add songs from any menu.' }),
        h('button', { type: 'button', class: 'btn btn-light', text: 'Create playlist', onclick: createPlaylist }),
      ),
    );
  }
  body.replaceChildren(...parts);
  markCurrentLinks(location.pathname);
}

function markCurrentLinks(path) {
  const p = path.length > 1 ? path.replace(/\/$/, '') : path;
  for (const a of $$('a[data-nav], .home-btn')) {
    const href = a.getAttribute('href');
    if (href === p) a.setAttribute('aria-current', 'page');
    else a.removeAttribute('aria-current');
  }
}
