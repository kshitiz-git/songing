// DOM helpers. Every string from the API goes in through h() / textContent, never innerHTML.
// Icons are built with createElementNS from the static ICONS table below (our own paths).

const SVG_NS = 'http://www.w3.org/2000/svg';

/** Build an element. props: class, text, dataset, on<event> handlers, any attribute. Children: strings, nodes, arrays. */
export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) {
    for (const [key, val] of Object.entries(props)) {
      if (key.startsWith('aria-')) {
        if (val != null) el.setAttribute(key, String(val));
        continue;
      }
      if (val == null || val === false) continue;
      if (key === 'class') el.className = val;
      else if (key === 'text') el.textContent = val;
      else if (key === 'dataset') Object.assign(el.dataset, val);
      else if (key === 'value' || key === 'checked') el[key] = val;
      else if (key.startsWith('on') && typeof val === 'function') el.addEventListener(key.slice(2), val);
      else el.setAttribute(key, val === true ? (key === 'draggable' ? 'true' : '') : String(val));
    }
  }
  append(el, children);
  return el;
}

function append(parent, children) {
  for (const c of children) {
    if (c == null || c === false) continue;
    if (Array.isArray(c)) append(parent, c);
    else if (c instanceof Node) parent.append(c);
    else parent.append(document.createTextNode(String(c)));
  }
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---------- icons (24x24, fill: currentColor) ----------
const ICONS = {
  play: 'M8 5v14l11-7z',
  pause: 'M6 19h4V5H6v14zm8-14v14h4V5h-4z',
  next: 'M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z',
  prev: 'M6 6h2v12H6zm3.5 6l8.5 6V6z',
  shuffle: 'M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z',
  repeat: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z',
  repeatOne: 'M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4zm-4-2V9h-1l-2 1v1h1.5v4H13z',
  volume: 'M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0 0 14 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z',
  volumeLow: 'M18.5 12A4.5 4.5 0 0 0 16 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z',
  volumeMute: 'M16.5 12A4.5 4.5 0 0 0 14 7.97v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51A8.8 8.8 0 0 0 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06a8.99 8.99 0 0 0 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z',
  heart: 'M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z',
  heartFill: 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z',
  home: 'M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z',
  search: 'M15.5 14h-.79l-.28-.27A6.47 6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  library: 'M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 5h-3v5.5a2.5 2.5 0 1 1-2.5-2.5c.57 0 1.08.19 1.5.51V5h4v2zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z',
  plus: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
  more: 'M6 10c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm12 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm-6 0c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z',
  queue: 'M15 6H3v2h12V6zm0 4H3v2h12v-2zM3 16h8v-2H3v2zM17 6v8.18c-.31-.11-.65-.18-1-.18-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3V8h3V6h-5z',
  queueAdd: 'M14 10H2v2h12v-2zm0-4H2v2h12V6zm4 8v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zM2 16h8v-2H2v2z',
  clock: 'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z',
  upload: 'M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z',
  trash: 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
  edit: 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a.996.996 0 0 0 0-1.41l-2.34-2.34a.996.996 0 0 0-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
  up: 'M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z',
  down: 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6z',
  back: 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
  grip: 'M11 18c0 1.1-.9 2-2 2s-2-.9-2-2 .9-2 2-2 2 .9 2 2zm-2-8c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0-6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm6 4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z',
  close: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  note: 'M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z',
  person: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  menu: 'M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z',
  check: 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z',
  album: 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-5.5c-.55 0-1 .45-1 1s.45 1 1 1 1-.45 1-1-.45-1-1-1z',
  info: 'M11 7h2v2h-2zm0 4h2v6h-2zm1-9C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z',
  list: 'M3 13h2v-2H3v2zm0 4h2v-2H3v2zm0-8h2V7H3v2zm4 4h14v-2H7v2zm0 4h14v-2H7v2zM7 7v2h14V7H7z',
};

export function icon(name, size) {
  const d = ICONS[name];
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('class', 'ico');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  if (size) {
    svg.setAttribute('width', size);
    svg.setAttribute('height', size);
  }
  const path = document.createElementNS(SVG_NS, 'path');
  path.setAttribute('d', d || '');
  svg.append(path);
  return svg;
}

/** Fill every <i data-icon="name"> inside root with its svg (used for the static shell in index.html). */
export function hydrateIcons(root = document) {
  for (const el of root.querySelectorAll('[data-icon]')) {
    el.replaceChildren(icon(el.dataset.icon));
    el.removeAttribute('data-icon');
  }
}

/** Icon-only button. label becomes aria-label (and the tooltip). */
export function iconButton(name, label, props = {}) {
  const { class: cls = '', ...rest } = props;
  return h('button', { type: 'button', class: `icon-btn ${cls}`.trim(), 'aria-label': label, title: label, ...rest }, icon(name));
}

// ---------- formatting ----------
export function fmtTime(sec) {
  sec = Number.isFinite(sec) && sec > 0 ? Math.floor(sec) : 0;
  const s = String(sec % 60).padStart(2, '0');
  const m = Math.floor(sec / 60) % 60;
  const hr = Math.floor(sec / 3600);
  return hr ? `${hr}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/** "1 hr 5 min" / "12 min 30 sec" for totals. */
export function fmtTotal(sec) {
  sec = Math.round(Number(sec) || 0);
  const hr = Math.floor(sec / 3600);
  const min = Math.floor((sec % 3600) / 60);
  if (hr) return `${hr} hr ${min} min`;
  if (min) return `${min} min ${sec % 60} sec`;
  return `${sec} sec`;
}

export const plural = (n, one, many = one + 's') => `${n} ${n === 1 ? one : many}`;
export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

export function debounce(fn, ms) {
  let t;
  const wrapped = (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
  wrapped.cancel = () => clearTimeout(t);
  return wrapped;
}

let uidN = 0;
export const uid = (prefix = 'id') => `${prefix}-${++uidN}`;

// ---------- covers ----------
// Hex colours from the API, or the hsl() pairs colorsFromText() makes for genre tiles.
const COLOR = /^(#[0-9a-fA-F]{3,8}|hsl\(\d{1,3} \d{1,3}% \d{1,3}%\))$/;
const FALLBACK_COLORS = ['#3b1f6e', '#1f6e4a'];

export function safeColors(colors) {
  if (Array.isArray(colors) && colors.length >= 2 && COLOR.test(colors[0]) && COLOR.test(colors[1])) return [colors[0], colors[1]];
  return FALLBACK_COLORS;
}

/** Only same-origin paths and http(s) URLs may reach href / src. */
export function safeUrl(u) {
  if (typeof u !== 'string' || !u) return null;
  if (u.startsWith('/') && !u.startsWith('//')) return u;
  try {
    const url = new URL(u);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null;
  } catch {
    return null;
  }
}

const COVER_ICON = { song: 'note', album: 'album', artist: 'person', playlist: 'list', playlistLiked: 'heartFill' };

/**
 * Square (or round) cover. Uses cover_url / image_url, a 2x2 mosaic from cover_urls,
 * or a gradient from item.colors. The gradient always sits underneath, so a broken image falls back to it.
 */
export function cover(item, { kind = 'song', round = false, cls = '' } = {}) {
  const [c1, c2] = safeColors(item && item.colors);
  const el = h('div', { class: `cover cover-${kind}${round ? ' round' : ''} ${cls}`.trim(), 'aria-hidden': 'true' });
  el.style.setProperty('--c1', c1);
  el.style.setProperty('--c2', c2);

  let urls = [];
  if (item) {
    if (item.cover_url) urls = [item.cover_url];
    else if (item.image_url) urls = [item.image_url];
    else if (Array.isArray(item.cover_urls)) urls = item.cover_urls.slice(0, 4);
  }
  urls = urls.map(safeUrl).filter(Boolean);
  if (urls.length > 1 && urls.length < 4) urls = urls.slice(0, 1);

  const markGradient = () => {
    if (!el.querySelector('img')) {
      el.classList.add('is-gradient');
      if (!el.querySelector('.cover-glyph')) el.append(h('span', { class: 'cover-glyph' }, icon(COVER_ICON[kind] || 'note')));
    }
  };

  if (urls.length === 0) {
    markGradient();
  } else {
    if (urls.length === 4) el.classList.add('mosaic');
    for (const src of urls) {
      const img = h('img', { src, alt: '', loading: 'lazy', decoding: 'async', draggable: 'false' });
      img.addEventListener('error', () => {
        img.remove();
        markGradient();
      });
      el.append(img);
    }
  }
  return el;
}

/** Gradient + glyph tile (Liked songs etc). */
export function tile(name, c1, c2, cls = '') {
  const el = h('div', { class: `cover is-gradient tile ${cls}`.trim(), 'aria-hidden': 'true' }, h('span', { class: 'cover-glyph' }, icon(name)));
  el.style.setProperty('--c1', c1);
  el.style.setProperty('--c2', c2);
  return el;
}

/** Stable hue-based colour pair for text-only things (genre tiles). */
export function colorsFromText(text) {
  let n = 0;
  for (const ch of String(text)) n = (n * 31 + ch.codePointAt(0)) >>> 0;
  const hue = n % 360;
  return [`hsl(${hue} 62% 38%)`, `hsl(${(hue + 40) % 360} 70% 22%)`];
}
