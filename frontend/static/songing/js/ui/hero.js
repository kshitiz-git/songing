// Page header for album / artist / playlist / library pages, plus the big green play button.
import { h, icon, safeColors } from '../dom.js';
import { player } from '../player.js';

/** hero({kind, title, coverEl, meta: Node[], description, round}) */
export function hero({ kind, title, coverEl, meta = [], description = '', round = false }) {
  return h(
    'header',
    { class: `hero${round ? ' hero-round' : ''}` },
    h('div', { class: 'hero-cover' }, coverEl),
    h(
      'div',
      { class: 'hero-text' },
      h('p', { class: 'hero-kind', text: kind }),
      h('h1', { class: `hero-title${title.length > 28 ? ' is-long' : ''}`, text: title }),
      description ? h('p', { class: 'hero-desc', text: description }) : null,
      meta.length ? h('p', { class: 'hero-meta' }, meta) : null,
    ),
  );
}

/** Interleave meta items with dots; falsy items are dropped. */
export function metaList(parts) {
  const out = [];
  for (const part of parts.filter(Boolean)) {
    if (out.length) out.push(h('span', { class: 'dot', 'aria-hidden': 'true', text: '·' }));
    out.push(part);
  }
  return out;
}

/** Wrapper for a detail page: the item's colours wash the top of the page (see .detail in app.css). */
export function detail(colors, ...children) {
  const [c1, c2] = safeColors(colors);
  const el = h('div', { class: 'detail' }, ...children);
  el.style.setProperty('--c1', c1);
  el.style.setProperty('--c2', c2);
  return el;
}

/** Green circle. When one of `getSongs()` is already playing it toggles pause instead of restarting. */
export function bigPlay(getSongs, label = 'Play') {
  const btn = h('button', { type: 'button', class: 'big-play', 'aria-label': label, title: label });
  const inList = () => {
    const cur = player.song;
    return !!cur && getSongs().some((s) => s.id === cur.id);
  };
  const paint = () => {
    const playing = player.playing && inList();
    btn.replaceChildren(icon(playing ? 'pause' : 'play'));
    const l = playing ? 'Pause' : label;
    btn.setAttribute('aria-label', l);
    btn.title = l;
  };
  btn.addEventListener('click', () => {
    if (inList()) player.togglePlay();
    else player.playAll(getSongs());
  });
  const onChange = () => {
    if (!btn.isConnected) {
      player.removeEventListener('song', onChange);
      player.removeEventListener('state', onChange);
      return;
    }
    paint();
  };
  player.addEventListener('song', onChange);
  player.addEventListener('state', onChange);
  paint();
  return btn;
}
