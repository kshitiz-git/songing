import { h, cover, fmtTotal, plural } from '../dom.js';
import { api } from '../api.js';
import { songList } from '../ui/songlist.js';
import { hero, detail, bigPlay, metaList } from '../ui/hero.js';
import { credits } from '../ui/credits.js';
import { emptyState } from '../ui/empty.js';

export const load = (ctx) => api(`/api/albums/${ctx.params.id}/`, { signal: ctx.signal });

export function render(d, ctx) {
  ctx.setTitle(d.title);
  const songs = d.songs || [];
  const list = songList(songs, { showAlbum: false });
  const total = songs.reduce((n, s) => n + (Number(s.duration) || 0), 0);

  const meta = metaList([
    d.artist ? h('a', { class: 'strong', href: `/artist/${d.artist.id}`, text: d.artist.name }) : null,
    d.year ? String(d.year) : null,
    plural(songs.length, 'song'),
    songs.length ? fmtTotal(total) : null,
  ]);

  return detail(
    d.colors,
    hero({ kind: 'Album', title: d.title, coverEl: cover(d, { kind: 'album' }), meta }),
    songs.length
      ? [h('div', { class: 'actions' }, bigPlay(() => list.songs(), `Play ${d.title}`)), list.el, credits(songs)]
      : emptyState({ title: 'No songs in this album yet' }),
  );
}
