import { h, icon, colorsFromText, plural } from '../dom.js';
import { api } from '../api.js';
import { songList } from '../ui/songlist.js';
import { pager } from '../ui/pager.js';
import { hero, detail, bigPlay, metaList } from '../ui/hero.js';
import { emptyState } from '../ui/empty.js';

export const load = (ctx) => api(`/api/songs/?genre=${encodeURIComponent(ctx.params.name)}`, { signal: ctx.signal });

export function render(page, ctx) {
  const name = ctx.params.name;
  ctx.setTitle(name);
  const [c1, c2] = colorsFromText(name);
  const songs = page.results || [];
  const list = songList(songs);

  const art = h('div', { class: 'cover is-gradient tile', 'aria-hidden': 'true' }, h('span', { class: 'cover-glyph' }, icon('note')));
  art.style.setProperty('--c1', c1);
  art.style.setProperty('--c2', c2);

  const body = songs.length
    ? [h('div', { class: 'actions' }, bigPlay(() => list.songs(), `Play ${name}`)), list.el, pager(list, page.next, { signal: ctx.signal })]
    : [emptyState({ title: `No ${name} songs yet`, text: 'Try another genre.', action: { label: 'Browse all genres', href: '/search' } })];

  return detail(
    [c1, c2],
    hero({ kind: 'Genre', title: name, coverEl: art, meta: metaList([page.count != null ? plural(page.count, 'song') : null]) }),
    ...body,
  );
}
