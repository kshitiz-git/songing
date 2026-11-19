import { h, cover, plural } from '../dom.js';
import { api } from '../api.js';
import { songList } from '../ui/songlist.js';
import { albumCard, shelf } from '../ui/cards.js';
import { hero, detail, bigPlay, metaList } from '../ui/hero.js';
import { credits } from '../ui/credits.js';

export const load = (ctx) => api(`/api/artists/${ctx.params.id}/`, { signal: ctx.signal });

export function render(d, ctx) {
  ctx.setTitle(d.name);
  const top = d.top_songs || [];
  const albums = d.albums || [];
  const list = songList(top);

  const parts = [hero({ kind: 'Artist', title: d.name, round: true, coverEl: cover(d, { kind: 'artist', round: true }), meta: metaList([plural(d.song_count ?? top.length, 'song')]) })];
  if (top.length) {
    parts.push(
      h('div', { class: 'actions' }, bigPlay(() => list.songs(), `Play ${d.name}`)),
      h('section', { class: 'block', 'aria-labelledby': 'artist-top' }, h('h2', { class: 'shelf-title', id: 'artist-top', text: 'Popular' }), list.el),
    );
  }
  if (albums.length) parts.push(shelf('Albums', albums.map(albumCard), { id: 'artist-albums' }));
  if (d.bio) parts.push(h('section', { class: 'block about', 'aria-labelledby': 'artist-about' }, h('h2', { class: 'shelf-title', id: 'artist-about', text: 'About' }), h('p', { class: 'bio', text: d.bio })));
  parts.push(credits(top));
  return detail(d.colors, ...parts);
}
