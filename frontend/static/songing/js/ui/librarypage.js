// Shared layout for Liked songs / Recently played / My uploads.
import { h, tile, plural } from '../dom.js';
import { store } from '../store.js';
import { songList } from './songlist.js';
import { pager } from './pager.js';
import { hero, detail, bigPlay, metaList } from './hero.js';
import { emptyState } from './empty.js';

/**
 * libraryPage({title, kind, glyph, colors, page, empty, listOptions, extraActions, signal})
 * page: a paginated response ({count,next,results}) or a plain array.
 */
export function libraryPage({ title, kind, glyph, colors, page, empty, listOptions = {}, extraActions = [], signal }) {
  const songs = Array.isArray(page) ? page : page.results || [];
  const next = Array.isArray(page) ? null : page.next;
  const count = Array.isArray(page) ? songs.length : page.count ?? songs.length;

  const emptyEl = emptyState(empty);
  const list = songList(songs, {
    ...listOptions,
    onChange: () => {
      emptyEl.hidden = list.count() > 0;
      body.hidden = list.count() === 0;
      if (listOptions.onChange) listOptions.onChange();
    },
  });
  const body = h('div', {}, list.el, pager(list, next, { signal }));
  body.hidden = songs.length === 0;
  emptyEl.hidden = songs.length > 0;

  return detail(
    colors,
    hero({
      kind,
      title,
      coverEl: tile(glyph, colors[0], colors[1]),
      meta: metaList([store.user ? h('span', { class: 'strong', text: store.user.username }) : null, plural(count, 'song')]),
    }),
    h('div', { class: 'actions' }, bigPlay(() => list.songs(), `Play ${title}`), ...extraActions),
    emptyEl,
    body,
  );
}
