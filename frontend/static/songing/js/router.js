// History-API router. Django serves the same page for every route; this swaps the content of <main>.
//
// A page module exports:
//   load(ctx)            optional, async: fetch data (use ctx.signal)
//   render(data, ctx)    returns a Node or {el, destroy?, update?(data, ctx)}
// ctx: {path, query, params, signal, name, setTitle(t), isCurrent()}
import { h } from './dom.js';
import { ApiError } from './api.js';
import { store, emit } from './store.js';

const routes = [
  { name: 'home', re: /^\/$/, load: () => import('./pages/home.js') },
  { name: 'search', re: /^\/search\/?$/, live: true, load: () => import('./pages/search.js') },
  { name: 'genre', re: /^\/genre\/([^/]+)\/?$/, keys: ['name'], load: () => import('./pages/genre.js') },
  { name: 'album', re: /^\/album\/(\d+)\/?$/, keys: ['id'], load: () => import('./pages/album.js') },
  { name: 'artist', re: /^\/artist\/(\d+)\/?$/, keys: ['id'], load: () => import('./pages/artist.js') },
  { name: 'playlist', re: /^\/playlist\/(\d+)\/?$/, keys: ['id'], load: () => import('./pages/playlist.js') },
  { name: 'liked', re: /^\/liked\/?$/, auth: true, load: () => import('./pages/liked.js') },
  { name: 'recent', re: /^\/recent\/?$/, auth: true, load: () => import('./pages/recent.js') },
  { name: 'uploads', re: /^\/uploads\/?$/, auth: true, load: () => import('./pages/uploads.js') },
  { name: 'upload', re: /^\/upload\/?$/, auth: true, load: () => import('./pages/upload.js') },
  { name: 'login', re: /^\/login\/?$/, load: () => import('./pages/auth.js') },
  { name: 'signup', re: /^\/signup\/?$/, load: () => import('./pages/auth.js') },
];
const NOT_FOUND = { name: 'notfound', load: () => import('./pages/notfound.js') };

let current = null; // {route, view}
let token = 0;
let controller = null;

const mainEl = () => document.getElementById('main');

function matchRoute(pathname) {
  for (const route of routes) {
    const m = route.re.exec(pathname);
    if (!m) continue;
    const params = {};
    try {
      (route.keys || []).forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1])));
    } catch {
      return null; // malformed %-escape
    }
    return { route, params };
  }
  return null;
}

export function setTitle(title) {
  document.title = title ? `${title} · Songing` : 'Songing';
  const ann = document.getElementById('route-announcer');
  if (ann) ann.textContent = title || 'Songing';
}

/** Allow only in-app paths as a post-login target. */
export function safeNext(raw, fallback = '/') {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return fallback;
  if (/^\/(api|static|media|admin)(\/|$)/.test(raw)) return fallback;
  return raw;
}

export const loginUrl = (next) => `/login?next=${encodeURIComponent(next || location.pathname + location.search)}`;

export function navigate(to, { replace = false, focus = !replace, force = false } = {}) {
  const url = new URL(to, location.origin);
  if (url.origin !== location.origin) {
    location.href = to;
    return Promise.resolve();
  }
  const target = url.pathname + url.search;
  if (!force && target === location.pathname + location.search) {
    const m = mainEl();
    if (m) m.scrollTo({ top: 0 });
    return Promise.resolve();
  }
  history[replace ? 'replaceState' : 'pushState']({}, '', target);
  return render({ focus });
}

export const reload = () => render({ reload: true });

function loadingView() {
  return h('div', { class: 'loading', role: 'status' }, h('span', { class: 'spinner' }), h('span', { class: 'sr-only', text: 'Loading' }));
}

function destroyCurrent() {
  if (current && current.view && current.view.destroy) {
    try {
      current.view.destroy();
    } catch (err) {
      console.error(err);
    }
  }
  current = null;
}

async function showError(root, err, retry) {
  if (err instanceof ApiError && err.status === 404) {
    const mod = await NOT_FOUND.load();
    setTitle('Not found');
    root.replaceChildren(mod.render());
    return;
  }
  console.error(err);
  root.replaceChildren(
    h(
      'div',
      { class: 'empty' },
      h('h1', { class: 'empty-title', text: 'Something went wrong' }),
      h('p', { class: 'empty-text', text: err instanceof ApiError ? err.message : 'The page could not be loaded.' }),
      h('button', { type: 'button', class: 'btn btn-light', text: 'Try again', onclick: retry }),
    ),
  );
}

async function render({ focus = false, reload = false } = {}) {
  const my = ++token;
  if (controller) controller.abort();
  controller = new AbortController();
  const url = new URL(location.href);
  const found = matchRoute(url.pathname);
  const route = found ? found.route : NOT_FOUND;

  if (route.auth && !store.user) {
    return navigate(loginUrl(url.pathname + url.search), { replace: true });
  }

  const ctx = {
    path: url.pathname,
    query: url.searchParams,
    params: found ? found.params : {},
    name: route.name,
    signal: controller.signal,
    setTitle,
    isCurrent: () => my === token,
  };
  emit('route', { path: ctx.path, query: ctx.query, name: route.name });
  if (route.name === 'notfound') setTitle('Page not found');

  let mod;
  try {
    mod = await route.load();
  } catch (err) {
    console.error(err);
    mainEl().replaceChildren(h('div', { class: 'empty' }, h('h1', { class: 'empty-title', text: 'Could not load this page' })));
    return;
  }
  if (my !== token) return;

  // Same live route (search): update in place instead of rebuilding.
  if (!reload && route.live && current && current.route === route && current.view.update) {
    try {
      const data = mod.load ? await mod.load(ctx) : undefined;
      if (my !== token) return;
      current.view.update(data, ctx);
    } catch (err) {
      if (err && err.name === 'AbortError') return;
      console.error(err);
      const { toast } = await import('./ui/toast.js');
      toast(err instanceof ApiError ? err.message : 'Search failed.', { kind: 'error' });
    }
    return;
  }

  destroyCurrent();
  const m = mainEl();
  const root = h('div', { class: 'page', 'data-page': route.name }, loadingView());
  m.replaceChildren(root);
  m.scrollTop = 0;

  try {
    const data = mod.load ? await mod.load(ctx) : undefined;
    if (my !== token) return;
    const out = mod.render(data, ctx);
    const view = out instanceof Node ? { el: out } : out;
    root.replaceChildren(view.el);
    current = { route, view };
  } catch (err) {
    if (my !== token || (err && err.name === 'AbortError')) return;
    if (err instanceof ApiError && (err.status === 401 || err.status === 403) && route.auth) {
      return navigate(loginUrl(url.pathname + url.search), { replace: true });
    }
    if (route.name !== 'notfound' && !(err instanceof ApiError && err.status === 404)) setTitle('Error');
    await showError(root, err, () => render({ focus: false, reload: true }));
  }
  if (my === token && focus) m.focus({ preventScroll: true });
}

function onClick(e) {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
  const a = e.target instanceof Element ? e.target.closest('a[href]') : null;
  if (!a) return;
  if ((a.target && a.target !== '_self') || a.hasAttribute('download')) return;
  const url = new URL(a.href, location.href);
  if (url.origin !== location.origin) return;
  if (/^\/(api|static|media|admin)(\/|$)/.test(url.pathname)) return;
  if (url.hash && url.pathname === location.pathname && url.search === location.search) return;
  e.preventDefault();
  navigate(url.pathname + url.search);
}

export function start() {
  document.addEventListener('click', onClick);
  window.addEventListener('popstate', () => render({ focus: false }));
  return render({ focus: false });
}
